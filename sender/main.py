from __future__ import annotations

import argparse
import asyncio
import contextlib
import json
import math
import platform
import re
import signal
import sys
import time
from dataclasses import dataclass, replace
from pathlib import Path
from typing import TYPE_CHECKING, Any

from commands.context import CommandContext
from commands.registry import execute
from config import Config

if TYPE_CHECKING:
    from bleak import BleakClient
    from bleak.backends.device import BLEDevice

PERCENT_MIN = 0
PERCENT_MAX = 100
SENDER_DIR = Path(__file__).resolve().parent

if sys.version_info < (3, 12):
    print(
        "Python 3.12 or 3.13 is required. Run `uv sync` in the sender directory, "
        "then start this tool with `uv run python main.py ...`.",
        file=sys.stderr,
    )
    raise SystemExit(1)


@dataclass(frozen=True)
class Metrics:
    cpu: int
    memory: int


class Logger:
    def __init__(self, verbose: bool = False) -> None:
        self.verbose = verbose

    def info(self, message: str) -> None:
        print(f"[info] {message}")

    def debug(self, message: str) -> None:
        if self.verbose:
            print(f"[debug] {message}")

    def warn(self, message: str) -> None:
        print(f"[warn] {message}", file=sys.stderr)

    def error(self, message: str) -> None:
        print(f"[error] {message}", file=sys.stderr)


def clamp_percent(value: Any) -> int:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return 0

    if not math.isfinite(number):
        return 0

    return min(PERCENT_MAX, max(PERCENT_MIN, round_half_up(number)))


def round_half_up(value: float) -> int:
    return int(math.floor(value + 0.5))


def format_timestamp(timestamp: float | None = None) -> int:
    if timestamp is None:
        timestamp = time.time()

    try:
        number = float(timestamp)
    except (TypeError, ValueError):
        return 0

    if not math.isfinite(number):
        return 0

    return math.floor(number)


def format_timezone_offset_hours(value: Any = 8) -> str:
    try:
        number = int(value)
    except (TypeError, ValueError):
        return "+8"

    return f"+{number}" if number >= 0 else str(number)


def encode_metrics_json(
    metrics: Metrics,
    *,
    include_time: bool = False,
    timezone_offset_hours: int = 8,
    timestamp: float | None = None,
) -> str:
    data: dict[str, Any] = {
        "cpu": clamp_percent(metrics.cpu),
        "memory": clamp_percent(metrics.memory),
    }

    if include_time:
        data["timestamp"] = format_timestamp(timestamp)
        data["timezone"] = format_timezone_offset_hours(timezone_offset_hours)

    return encode_json_line({"type": "metrics.update", "data": data})


def encode_json_line(payload: dict[str, Any]) -> str:
    return json.dumps(payload, ensure_ascii=True, separators=(",", ":")) + "\n"


def collect_metrics() -> Metrics:
    try:
        import psutil
    except ModuleNotFoundError as error:
        raise RuntimeError(
            "Missing dependency: psutil. Run `uv sync` in the sender directory, "
            "then start this tool with `uv run python main.py ...`."
        ) from error

    cpu_percent = psutil.cpu_percent(interval=0.1)
    memory = psutil.virtual_memory()
    active_memory = getattr(memory, "active", None)
    if active_memory is None:
        active_memory = getattr(memory, "used", 0)
    memory_percent = (
        (float(active_memory) / float(memory.total)) * 100 if memory.total else 0
    )

    return Metrics(
        cpu=clamp_percent(cpu_percent),
        memory=clamp_percent(memory_percent),
    )


def resolve_pages_config_path(config: Config) -> Path:
    path = Path(config.pages_config_path)
    if path.is_absolute():
        return path

    return SENDER_DIR / path


def load_pages_config(config: Config) -> dict[str, Any]:
    path = resolve_pages_config_path(config)
    with path.open("r", encoding="utf-8") as file:
        payload = json.load(file)

    validate_pages_config(payload, config)
    return payload


def validate_pages_config(payload: Any, config: Config) -> None:
    if not isinstance(payload, dict):
        raise ValueError("pages config must be a JSON object")

    pages = payload.get("pages")
    if not isinstance(pages, list):
        raise ValueError("pages config requires a pages array")

    if len(pages) > config.max_pages:
        raise ValueError(f"pages config supports at most {config.max_pages} pages")

    for index, page in enumerate(pages, start=1):
        if not isinstance(page, dict):
            raise ValueError(f"page {index} must be an object")

        name = page.get("name")
        if not isinstance(name, str) or not name.strip():
            raise ValueError(f"page {index} requires a non-empty name")

        actions = page.get("actions")
        if not isinstance(actions, list):
            raise ValueError(f"page {index} requires an actions array")

        actions_by_event: dict[str, Any] = {}
        for action in actions:
            if not isinstance(action, dict):
                raise ValueError(f"page {index} action must be an object")

            event = action.get("event")
            label = action.get("label")
            op_code = action.get("op")
            if not all(isinstance(value, str) and value.strip() for value in [event, label, op_code]):
                raise ValueError(f"page {index} actions require event, label, and op strings")

            if not op_code.startswith("OP-"):
                raise ValueError(f"page {index} action op must start with OP-")

            if len(label) > config.max_page_text_length or len(op_code) > config.max_page_text_length:
                raise ValueError(
                    f"page {index} action label/op must be <= {config.max_page_text_length} chars"
                )

            actions_by_event[event] = action

        for required_event in ["a.click", "a.double"]:
            if required_event not in actions_by_event:
                raise ValueError(f"page {index} requires {required_event} action")


def encode_pages_config(payload: dict[str, Any]) -> str:
    return encode_json_line({"type": "pages.config", "data": payload})


def encode_ping() -> str:
    return encode_json_line({"type": "ping"})


def merge_cli_options(config: Config, args: argparse.Namespace) -> Config:
    updates: dict[str, Any] = {}
    cli_mapping = {
        "port": "port",
        "baud": "baud_rate",
        "interval": "interval_ms",
        "transport": "transport",
        "ble_name": "ble_name",
        "ble_id": "ble_id",
        "ble_scan_timeout": "ble_scan_timeout_ms",
        "ble_connect_delay": "ble_connect_delay_ms",
        "ble_discovery_timeout": "ble_discovery_timeout_ms",
        "ble_discovery_retries": "ble_discovery_retries",
        "ble_discovery_retry_delay": "ble_discovery_retry_delay_ms",
        "pages_config": "pages_config_path",
        "heartbeat": "heartbeat_ms",
        "verbose": "verbose",
    }

    for arg_name, field_name in cli_mapping.items():
        value = getattr(args, arg_name)
        if value is not None:
            updates[field_name] = value

    if args.no_pages:
        updates["pages_enabled"] = False

    return replace(config, **updates)


def validate_config(config: Config) -> Config:
    errors: list[str] = []
    transport = str(config.transport or "serial").strip().lower()
    port = str(config.port or "").strip()
    ble_name = str(config.ble_name or "").strip()
    ble_id = str(config.ble_id or "").strip()

    if not isinstance(config.baud_rate, int) or config.baud_rate <= 0:
        errors.append("baudRate must be a positive integer")

    if (
        not isinstance(config.interval_ms, int)
        or config.interval_ms < config.min_interval_ms
    ):
        errors.append(f"intervalMs must be an integer >= {config.min_interval_ms}")

    if (
        not isinstance(config.timezone_offset_hours, int)
        or config.timezone_offset_hours < config.min_timezone_offset_hours
        or config.timezone_offset_hours > config.max_timezone_offset_hours
    ):
        errors.append(
            "timezoneOffsetHours must be an integer between "
            f"{config.min_timezone_offset_hours} and {config.max_timezone_offset_hours}"
        )

    if transport == "serial" and not config.auto_select_port and not port:
        errors.append("port is required when autoSelectPort is false")

    if transport not in {"serial", "ble"}:
        errors.append('transport must be "serial" or "ble"')

    if transport == "ble" and is_unsupported_macos_ble_runtime():
        errors.append(
            "BLE on macOS is unstable with Python 3.14/CoreBluetooth. "
            "Use Python 3.12 or 3.13 for sender."
        )

    if (
        not isinstance(config.ble_scan_timeout_ms, int)
        or config.ble_scan_timeout_ms < config.min_ble_scan_timeout_ms
    ):
        errors.append(
            f"bleScanTimeoutMs must be an integer >= {config.min_ble_scan_timeout_ms}"
        )

    if (
        not isinstance(config.ble_connect_delay_ms, int)
        or config.ble_connect_delay_ms < config.min_ble_connect_delay_ms
    ):
        errors.append(
            f"bleConnectDelayMs must be an integer >= {config.min_ble_connect_delay_ms}"
        )

    if (
        not isinstance(config.ble_discovery_timeout_ms, int)
        or config.ble_discovery_timeout_ms < config.min_ble_discovery_timeout_ms
    ):
        errors.append(
            "bleDiscoveryTimeoutMs must be an integer >= "
            f"{config.min_ble_discovery_timeout_ms}"
        )

    if (
        not isinstance(config.ble_discovery_retries, int)
        or config.ble_discovery_retries < config.min_ble_discovery_retries
    ):
        errors.append(
            f"bleDiscoveryRetries must be an integer >= {config.min_ble_discovery_retries}"
        )

    if (
        not isinstance(config.ble_discovery_retry_delay_ms, int)
        or config.ble_discovery_retry_delay_ms < config.min_ble_discovery_retry_delay_ms
    ):
        errors.append(
            "bleDiscoveryRetryDelayMs must be an integer >= "
            f"{config.min_ble_discovery_retry_delay_ms}"
        )

    if (
        not isinstance(config.ble_write_chunk_bytes, int)
        or config.ble_write_chunk_bytes < config.min_ble_write_chunk_bytes
    ):
        errors.append(
            "bleWriteChunkBytes must be an integer >= "
            f"{config.min_ble_write_chunk_bytes}"
        )

    if (
        not isinstance(config.heartbeat_ms, int)
        or config.heartbeat_ms < config.min_heartbeat_ms
    ):
        errors.append(f"heartbeatMs must be an integer >= {config.min_heartbeat_ms}")

    if errors:
        raise ValueError(f"Invalid config: {'; '.join(errors)}")

    return replace(
        config,
        port=port,
        transport=transport,
        ble_name=ble_name,
        ble_id=ble_id,
        ble_service_uuid=str(config.ble_service_uuid or "").strip(),
        ble_metrics_characteristic_uuid=str(
            config.ble_metrics_characteristic_uuid or ""
        ).strip(),
        ble_command_characteristic_uuid=str(
            config.ble_command_characteristic_uuid or ""
        ).strip(),
        pages_config_path=str(config.pages_config_path or "").strip(),
        verbose=bool(config.verbose),
    )


def create_runtime_config(args: argparse.Namespace) -> Config:
    return validate_config(merge_cli_options(Config(), args))


def is_unsupported_macos_ble_runtime() -> bool:
    return platform.system() == "Darwin" and sys.version_info >= (3, 14)


@dataclass(frozen=True)
class SerialPortInfo:
    path: str
    manufacturer: str = ""
    vendor_id: str = ""
    product_id: str = ""


class ReconnectableSerialTransport:
    def __init__(self, preferred_path: str, baud_rate: int) -> None:
        self.preferred_path = preferred_path
        self.baud_rate = baud_rate
        self._serial: Any | None = None
        self._path = ""
        self._lock = asyncio.Lock()

    @property
    def path(self) -> str:
        return self._path

    async def open(self) -> None:
        if self._serial and self._serial.is_open:
            return

        async with self._lock:
            if self._serial and self._serial.is_open:
                return

            opened = await asyncio.to_thread(
                open_fresh_serial_port,
                self.preferred_path,
                self.baud_rate,
            )
            self._serial = opened[0]
            self._path = opened[1]

    async def write(self, line: str) -> None:
        await self.open()
        active_port = self._serial
        if not active_port:
            raise RuntimeError("Serial transport is not open")

        try:
            await asyncio.to_thread(write_serial_line, active_port, line)
        except Exception:
            if self._serial is active_port:
                self._serial = None
            raise

    async def readline(self) -> str:
        await self.open()
        active_port = self._serial
        if not active_port:
            raise RuntimeError("Serial transport is not open")

        try:
            data = await asyncio.to_thread(active_port.readline)
        except Exception:
            if self._serial is active_port:
                self._serial = None
            raise

        if isinstance(data, bytes):
            return data.decode("utf-8", errors="replace").strip()

        return str(data or "").strip()

    async def close(self) -> None:
        active_port = self._serial
        self._serial = None
        if active_port and active_port.is_open:
            await asyncio.to_thread(active_port.close)


class ReconnectableBleTransport:
    def __init__(self, config: Config) -> None:
        self.config = config
        self._client: BleakClient | None = None
        self._path = ""
        self._closed = False
        self._lock = asyncio.Lock()
        self._line_queue: asyncio.Queue[str] = asyncio.Queue()
        self._notify_buffer = ""
        self._notify_started = False

    @property
    def path(self) -> str:
        return self._path

    async def open(self) -> None:
        if self._client and self._client.is_connected:
            return

        async with self._lock:
            if self._client and self._client.is_connected:
                return

            client, label = await open_fresh_ble_connection(self.config)
            try:
                await self._start_notify(client)
            except Exception as error:
                print(
                    "[warn] BLE command notify unavailable; continuing write-only BLE "
                    f"session: {error}",
                    file=sys.stderr,
                )
                self._notify_started = False

            self._client = client
            self._path = label

    async def write(self, line: str) -> None:
        if self._closed:
            raise RuntimeError("BLE transport is closed")

        await self.open()
        active_client = self._client
        if not active_client:
            raise RuntimeError("BLE transport is not open")

        try:
            data = line.encode("utf-8")
            chunk_count = 0
            chunk_bytes = self.config.ble_write_chunk_bytes
            for offset in range(0, len(data), chunk_bytes):
                await active_client.write_gatt_char(
                    self.config.ble_metrics_characteristic_uuid,
                    data[offset:offset + chunk_bytes],
                    response=False,
                )
                chunk_count += 1
                await asyncio.sleep(0.01)
            if self.config.verbose and chunk_count > 1:
                print(f"[debug] BLE write chunks: {chunk_count}", file=sys.stderr)
        except Exception:
            self._client = None
            self._notify_started = False
            raise

    async def readline(self) -> str:
        await self.open()
        if not self._notify_started:
            await asyncio.sleep(1)
            return ""

        try:
            return await asyncio.wait_for(self._line_queue.get(), timeout=1)
        except asyncio.TimeoutError:
            return ""

    async def _start_notify(self, client: BleakClient) -> None:
        if self._notify_started:
            return

        await client.start_notify(
            self.config.ble_command_characteristic_uuid,
            self._handle_notify,
        )
        self._notify_started = True

    def _handle_notify(self, _: Any, data: bytearray) -> None:
        self._notify_buffer += bytes(data).decode("utf-8", errors="replace")
        while "\n" in self._notify_buffer:
            line, self._notify_buffer = self._notify_buffer.split("\n", 1)
            normalized = line.strip()
            if normalized:
                self._line_queue.put_nowait(normalized)

    async def close(self) -> None:
        self._closed = True
        active_client = self._client
        self._client = None
        self._notify_started = False
        self._notify_buffer = ""

        if active_client and active_client.is_connected:
            await active_client.disconnect()


def list_serial_ports() -> list[SerialPortInfo]:
    try:
        from serial.tools import list_ports
    except ModuleNotFoundError as error:
        raise RuntimeError(
            "Missing dependency: pyserial. Run `uv sync` in the sender directory, "
            "then start this tool with `uv run python main.py ...`."
        ) from error

    ports = []
    for port in list_ports.comports():
        vendor_id = f"{port.vid:04x}" if port.vid is not None else ""
        product_id = f"{port.pid:04x}" if port.pid is not None else ""
        ports.append(
            SerialPortInfo(
                path=port.device,
                manufacturer=port.manufacturer or "",
                vendor_id=vendor_id,
                product_id=product_id,
            )
        )
    return ports


def select_port(ports: list[SerialPortInfo], preferred_path: str = "") -> str:
    if not ports:
        raise RuntimeError("No serial ports found. Connect M5StickC Plus and try again.")

    if preferred_path:
        for port in ports:
            if port.path == preferred_path:
                return port.path

        raise RuntimeError(
            f'Serial port not found: {preferred_path}. Run "python main.py --list-ports" '
            "to see available ports."
        )

    candidates = [port for port in ports if is_likely_m5_port(port)]

    if len(candidates) == 1:
        return candidates[0].path

    if len(candidates) > 1:
        best_candidate = select_best_port_candidate(candidates)
        if best_candidate:
            return best_candidate.path

        paths = ", ".join(port.path for port in candidates)
        raise RuntimeError(
            f"Multiple likely M5 serial ports found: {paths}. Specify one with --port <path>."
        )

    raise RuntimeError(
        'Could not auto-select a serial port. Run "python main.py --list-ports" '
        "and specify --port <path>."
    )


def open_fresh_serial_port(
    preferred_path: str,
    baud_rate: int,
) -> tuple[Any, str]:
    try:
        import serial
    except ModuleNotFoundError as error:
        raise RuntimeError(
            "Missing dependency: pyserial. Run `uv sync` in the sender directory, "
            "then start this tool with `uv run python main.py ...`."
        ) from error

    path = select_port(list_serial_ports(), preferred_path)

    try:
        port = serial.Serial(port=path, baudrate=baud_rate, timeout=1, write_timeout=2)
    except serial.SerialException as error:
        raise create_serial_open_error(error, path) from error

    return port, path


def write_serial_line(port: Any, line: str) -> None:
    port.write(line.encode("utf-8"))
    port.flush()


Transport = ReconnectableSerialTransport | ReconnectableBleTransport


def create_serial_open_error(error: Exception, path: str) -> RuntimeError:
    message = str(error)
    busy_tokens = ["resource busy", "busy", "cannot open", "access denied", "permission"]

    if any(token in message.lower() for token in busy_tokens):
        return RuntimeError(
            f"Cannot open serial port {path}: {message}. "
            "Close any app using this port, such as Arduino Serial Monitor, M5Burner, "
            f"screen, minicom, or another sender process. On macOS you can run: lsof {path}"
        )

    return RuntimeError(f"Cannot open serial port {path}: {message}")


def select_best_port_candidate(candidates: list[SerialPortInfo]) -> SerialPortInfo | None:
    tty_candidates = [
        port for port in candidates if str(port.path or "").startswith("/dev/tty.")
    ]
    if len(tty_candidates) == 1:
        return tty_candidates[0]

    return None


def is_likely_m5_port(port: SerialPortInfo) -> bool:
    manufacturer = str(port.manufacturer or "").lower()
    path = str(port.path or "").lower()
    vendor_id = str(port.vendor_id or "").lower()

    return (
        "/dev/tty.usbserial" in path
        or "/dev/tty.usbmodem" in path
        or manufacturer.find("wch") >= 0
        or manufacturer.find("silicon labs") >= 0
        or manufacturer.find("ftdi") >= 0
        or manufacturer.find("m5stack") >= 0
        or vendor_id in {"1a86", "10c4", "0403"}
    )


async def list_ble_devices(config: Config) -> list[BLEDevice]:
    return await scan_for_ble_devices(config, allow_multiple=True)


async def open_fresh_ble_connection(config: Config) -> tuple[BleakClient, str]:
    BleakClient, _ = load_bleak()
    last_error: Exception | None = None

    for attempt in range(1, config.ble_discovery_retries + 1):
        device = await select_ble_device(config)
        client = BleakClient(device)

        try:
            await client.connect()
            if config.ble_connect_delay_ms > 0:
                await asyncio.sleep(config.ble_connect_delay_ms / 1000)

            await wait_for_gatt_characteristic(client, config)
            return client, describe_ble_device(device)
        except Exception as error:
            last_error = error
            if client.is_connected:
                await client.disconnect()

            if attempt < config.ble_discovery_retries:
                await asyncio.sleep(config.ble_discovery_retry_delay_ms / 1000)

    raise last_error or RuntimeError("BLE connection failed.")


async def wait_for_gatt_characteristic(client: BleakClient, config: Config) -> None:
    async def discover() -> None:
        services = await get_client_services(client)
        metrics_characteristic = services.get_characteristic(
            config.ble_metrics_characteristic_uuid
        )
        if not metrics_characteristic:
            raise RuntimeError("BLE metrics characteristic not found on selected device.")
        command_characteristic = services.get_characteristic(
            config.ble_command_characteristic_uuid
        )
        if not command_characteristic:
            raise RuntimeError(
                "BLE command notify characteristic not found. "
                "Flash firmware with bidirectional BLE support."
            )

    try:
        await asyncio.wait_for(discover(), timeout=config.ble_discovery_timeout_ms / 1000)
    except asyncio.TimeoutError as error:
        raise RuntimeError(
            "BLE GATT discovery timed out. Try power-cycling the M5 device, "
            "toggling Bluetooth off/on, or increasing --ble-connect-delay."
        ) from error


async def get_client_services(client: BleakClient) -> Any:
    get_services = getattr(client, "get_services", None)
    if callable(get_services):
        return await get_services()

    services = getattr(client, "services", None)
    if services is None:
        raise RuntimeError("BLE GATT services are not available on selected device.")

    return services


async def select_ble_device(config: Config) -> BLEDevice:
    devices = await scan_for_ble_devices(config)

    if not devices:
        raise RuntimeError(
            "No BLE M5 monitor found. Make sure the device is powered on and advertising."
        )

    if config.ble_id or config.ble_name:
        return devices[0]

    if len(devices) == 1:
        return devices[0]

    labels = ", ".join(describe_ble_device(device) for device in devices)
    raise RuntimeError(
        f"Multiple BLE M5 monitors found: {labels}. Specify --ble-id or --ble-name."
    )


async def scan_for_ble_devices(
    config: Config,
    *,
    allow_multiple: bool = False,
) -> list[BLEDevice]:
    devices = await discover_ble_devices(config)

    matching: list[BLEDevice] = []
    seen: set[str] = set()

    for device, service_uuids in devices:
        if not matches_ble_device(device, config, service_uuids):
            continue

        key = normalize_id(device.address or device.name or "")
        if key in seen:
            continue

        seen.add(key)
        matching.append(device)

        if not allow_multiple and (config.ble_id or config.ble_name):
            break

    return matching


async def discover_ble_devices(config: Config) -> list[tuple[BLEDevice, list[str]]]:
    _, BleakScanner = load_bleak()
    timeout = config.ble_scan_timeout_ms / 1000
    service_uuids = [config.ble_service_uuid]

    try:
        discovered = await discover_ble_devices_with_advertisements(
            BleakScanner,
            timeout=timeout,
            service_uuids=service_uuids,
        )
        return discovered or await discover_ble_devices_with_advertisements(
            BleakScanner,
            timeout=timeout,
        )
    except TypeError:
        devices = await BleakScanner.discover(
            timeout=timeout,
            service_uuids=service_uuids,
        )
        if not devices:
            devices = await BleakScanner.discover(timeout=timeout)
        return [(device, get_device_service_uuids(device)) for device in devices]


async def discover_ble_devices_with_advertisements(
    scanner: Any,
    *,
    timeout: float,
    service_uuids: list[str] | None = None,
) -> list[tuple[BLEDevice, list[str]]]:
    discovered = await scanner.discover(
        timeout=timeout,
        service_uuids=service_uuids,
        return_adv=True,
    )
    return [
        (device, list(advertisement_data.service_uuids or []))
        for device, advertisement_data in discovered.values()
    ]


def load_bleak() -> tuple[Any, Any]:
    ensure_macos_bluetooth_usage_description()

    from bleak import BleakClient, BleakScanner

    return BleakClient, BleakScanner


def ensure_macos_bluetooth_usage_description() -> None:
    if platform.system() != "Darwin":
        return

    try:
        from Foundation import NSBundle
    except Exception:
        return

    info = NSBundle.mainBundle().infoDictionary()
    if info is None:
        return

    purpose = "M5StickC Plus PC Monitor uses Bluetooth to send PC metrics to the device."
    info["NSBluetoothAlwaysUsageDescription"] = purpose
    info["NSBluetoothPeripheralUsageDescription"] = purpose


def get_device_service_uuids(device: BLEDevice) -> list[str]:
    metadata = getattr(device, "metadata", {}) or {}
    return list(metadata.get("uuids", []) or [])


def matches_ble_device(
    device: BLEDevice,
    config: Config,
    service_uuids: list[str] | None = None,
) -> bool:
    if config.ble_id:
        ids = [
            normalize_id(value)
            for value in [device.address, getattr(device, "details", "")]
        ]
        if normalize_id(config.ble_id) not in ids:
            return False

    if config.ble_name and str(device.name or "") != config.ble_name:
        return False

    if config.ble_name or config.ble_id:
        return True

    if has_ble_service(service_uuids or [], config.ble_service_uuid):
        return True

    return str(device.name or "") == config.ble_default_device_name


def has_ble_service(service_uuids: list[str], expected_uuid: str) -> bool:
    advertised_services = {normalize_uuid(service_uuid) for service_uuid in service_uuids}
    return normalize_uuid(expected_uuid) in advertised_services


def normalize_uuid(value: Any) -> str:
    return str(value or "").replace("-", "").lower()


def normalize_id(value: Any) -> str:
    return str(value or "").replace(":", "").lower()


def describe_ble_device(device: BLEDevice) -> str:
    name = device.name or "unnamed"
    address = device.address or "unknown"
    rssi = getattr(device, "rssi", None)

    if rssi is None and hasattr(device, "metadata"):
        rssi = device.metadata.get("rssi")

    return f"{name} ({address}, rssi={rssi if rssi is not None else 'unknown'})"


async def open_transport(config: Config) -> Transport:
    if config.transport == "ble":
        transport = ReconnectableBleTransport(config)
    else:
        transport = ReconnectableSerialTransport(config.port, config.baud_rate)

    await transport.open()
    return transport


async def send_once(
    transport: Transport,
    logger: Logger,
    *,
    include_time: bool = False,
    timezone_offset_hours: int = 8,
) -> None:
    metrics = collect_metrics()
    line = encode_metrics_json(
        metrics,
        include_time=include_time,
        timezone_offset_hours=timezone_offset_hours,
    )

    await transport.write(line)
    logger.debug(f"write: {line.strip()}")


async def run_sender(config: Config, logger: Logger) -> None:
    transport = await open_transport(config)
    stop_event = asyncio.Event()
    sysinfo_enabled = asyncio.Event()
    immediate_metrics = asyncio.Event()

    def request_shutdown() -> None:
        stop_event.set()

    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, request_shutdown)
        except NotImplementedError:
            pass

    logger.info(f"using {config.transport} transport: {transport.path}")
    logger.info(f"sender started, interval: {config.interval_ms}ms")

    try:
        if config.pages_enabled:
            pages_payload = load_pages_config(config)
            line = encode_pages_config(pages_payload)
            await transport.write(line)
            logger.debug(f"write: {line.strip()}")
            logger.info(f"sent page config: {resolve_pages_config_path(config)}")

        tasks = [
            asyncio.create_task(
                command_reader_loop(
                    transport,
                    config,
                    logger,
                    stop_event,
                    sysinfo_enabled,
                    immediate_metrics,
                )
            ),
            asyncio.create_task(
                metrics_loop(
                    transport,
                    config,
                    logger,
                    stop_event,
                    sysinfo_enabled,
                    immediate_metrics,
                )
            ),
            asyncio.create_task(
                heartbeat_loop(
                    transport,
                    config,
                    logger,
                    stop_event,
                    sysinfo_enabled,
                )
            ),
        ]

        await stop_event.wait()
        for task in tasks:
            task.cancel()
        for task in tasks:
            with contextlib.suppress(asyncio.CancelledError):
                await task
    except KeyboardInterrupt:
        pass
    finally:
        logger.info("closing transport")
        await transport.close()


async def command_reader_loop(
    transport: Transport,
    config: Config,
    logger: Logger,
    stop_event: asyncio.Event,
    sysinfo_enabled: asyncio.Event,
    immediate_metrics: asyncio.Event,
) -> None:
    context = CommandContext(logger=logger, config=config)

    while not stop_event.is_set():
        try:
            line = await transport.readline()
        except Exception as error:
            logger.warn(f"read failed, retrying: {error}")
            await asyncio.sleep(1)
            continue

        if not line:
            continue

        logger.debug(f"read: {line}")
        op_code = parse_device_command_op(line)
        if not op_code:
            logger.debug(f"ignore unknown inbound line: {line}")
            continue

        if op_code == "OP-SYSINFO":
            sysinfo_enabled.set()
            immediate_metrics.set()
            logger.info("sysinfo enabled by device")
            continue

        if op_code == "OP-SYSINFO-STOP":
            sysinfo_enabled.clear()
            logger.info("sysinfo stopped by device")
            continue

        await execute(op_code, context)


def parse_device_command_op(line: str) -> str:
    normalized = line.strip()
    if not normalized:
        return ""

    if normalized.startswith("OP-"):
        return normalized

    try:
        payload = json.loads(normalized)
    except json.JSONDecodeError:
        return ""

    if payload.get("type") != "device.command":
        return ""

    data = payload.get("data") or {}
    op_code = data.get("op")
    return op_code if isinstance(op_code, str) else ""


async def metrics_loop(
    transport: Transport,
    config: Config,
    logger: Logger,
    stop_event: asyncio.Event,
    sysinfo_enabled: asyncio.Event,
    immediate_metrics: asyncio.Event,
) -> None:
    sent_time_sync = False

    while not stop_event.is_set():
        await wait_for_event_or_stop(sysinfo_enabled, stop_event)
        if stop_event.is_set():
            break

        immediate_metrics.clear()
        try:
            await send_once(
                transport,
                logger,
                include_time=not sent_time_sync,
                timezone_offset_hours=config.timezone_offset_hours,
            )
            sent_time_sync = True
        except Exception as error:
            logger.warn(f"send failed, retrying: {error}")

        done, _ = await asyncio.wait(
            wait_tasks := [
                asyncio.create_task(stop_event.wait()),
                asyncio.create_task(immediate_metrics.wait()),
                asyncio.create_task(wait_for_event_clear(sysinfo_enabled)),
            ],
            timeout=config.interval_ms / 1000,
            return_when=asyncio.FIRST_COMPLETED,
        )
        for task in wait_tasks:
            task.cancel()
        for task in wait_tasks:
            with contextlib.suppress(asyncio.CancelledError):
                await task


async def heartbeat_loop(
    transport: Transport,
    config: Config,
    logger: Logger,
    stop_event: asyncio.Event,
    sysinfo_enabled: asyncio.Event,
) -> None:
    while not stop_event.is_set():
        try:
            await asyncio.wait_for(stop_event.wait(), timeout=config.heartbeat_ms / 1000)
            break
        except asyncio.TimeoutError:
            pass

        if sysinfo_enabled.is_set():
            continue

        try:
            line = encode_ping()
            await transport.write(line)
            logger.debug(f"write: {line.strip()}")
        except Exception as error:
            logger.warn(f"heartbeat failed, retrying: {error}")


async def wait_for_event_or_stop(event: asyncio.Event, stop_event: asyncio.Event) -> None:
    while not event.is_set() and not stop_event.is_set():
        await asyncio.sleep(0.05)


async def wait_for_event_clear(event: asyncio.Event) -> None:
    while event.is_set():
        await asyncio.sleep(0.05)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="m5-monitor-sender",
        description="Send PC CPU and memory metrics to M5StickC Plus over USB serial or BLE.",
    )
    parser.add_argument("--transport", choices=["serial", "ble"], help="transport type")
    parser.add_argument("--port", help="serial port path")
    parser.add_argument("--baud", type=parse_integer, help="serial baud rate")
    parser.add_argument(
        "--interval",
        type=parse_integer,
        help="send interval in milliseconds",
    )
    parser.add_argument("--list-ports", action="store_true", help="list serial ports and exit")
    parser.add_argument(
        "--list-ble",
        action="store_true",
        help="scan BLE monitor devices and exit",
    )
    parser.add_argument("--ble-name", help="BLE device name to connect")
    parser.add_argument("--ble-id", help="BLE device id or address to connect")
    parser.add_argument(
        "--ble-scan-timeout",
        type=parse_integer,
        help="BLE scan timeout in milliseconds",
    )
    parser.add_argument(
        "--ble-connect-delay",
        type=parse_integer,
        help="delay after BLE connect before GATT discovery",
    )
    parser.add_argument(
        "--ble-discovery-timeout",
        type=parse_integer,
        help="BLE GATT discovery timeout in milliseconds",
    )
    parser.add_argument(
        "--ble-discovery-retries",
        type=parse_integer,
        help="BLE GATT discovery retry count",
    )
    parser.add_argument(
        "--ble-discovery-retry-delay",
        type=parse_integer,
        help="delay between BLE GATT discovery retries",
    )
    parser.add_argument("--no-pages", action="store_true", help="do not send pages config")
    parser.add_argument("--pages-config", help="path to pages JSON config")
    parser.add_argument(
        "--heartbeat",
        type=parse_integer,
        help="heartbeat interval in milliseconds when sysinfo is paused",
    )
    parser.add_argument("--verbose", action="store_true", default=None, help="enable debug logs")
    return parser


def parse_integer(value: str) -> int:
    normalized = str(value).strip()
    if not re.fullmatch(r"[+-]?\d+", normalized):
        raise argparse.ArgumentTypeError("must be an integer")

    try:
        return int(normalized)
    except ValueError as error:
        raise argparse.ArgumentTypeError("must be an integer") from error


def print_ports() -> None:
    ports = list_serial_ports()

    if not ports:
        print("No serial ports found.")
        return

    for port in ports:
        details = [
            f"manufacturer={port.manufacturer}" if port.manufacturer else "",
            f"vendorId={port.vendor_id}" if port.vendor_id else "",
            f"productId={port.product_id}" if port.product_id else "",
        ]
        detail_text = ", ".join(detail for detail in details if detail)
        suffix = f" ({detail_text})" if detail_text else ""
        print(f"{port.path}{suffix}")


async def print_ble_devices(config: Config) -> None:
    devices = await list_ble_devices(config)

    if not devices:
        print("No BLE monitor devices found.")
        return

    for device in devices:
        name = device.name or ""
        address = device.address or ""
        rssi = getattr(device, "rssi", None)
        if rssi is None and hasattr(device, "metadata"):
            rssi = device.metadata.get("rssi")

        details = [
            f"name={name}" if name else "",
            f"address={address}" if address else "",
            f"rssi={rssi}" if rssi is not None else "",
        ]
        detail_text = ", ".join(detail for detail in details if detail)
        suffix = f" ({detail_text})" if detail_text else ""
        print(f"{address or name}{suffix}")


async def async_main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    logger = Logger()

    try:
        if args.list_ports:
            print_ports()
            return 0

        config = create_runtime_config(args)
        logger = Logger(config.verbose)

        if args.list_ble:
            await print_ble_devices(config)
            return 0

        await run_sender(config, logger)
        return 0
    except Exception as error:
        logger.error(str(error))
        return 1


def main() -> None:
    raise SystemExit(asyncio.run(async_main()))


if __name__ == "__main__":
    main()
