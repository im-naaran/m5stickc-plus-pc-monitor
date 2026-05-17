from __future__ import annotations

from dataclasses import dataclass


BLE_SERVICE_UUID = "6e400001-b5a3-f393-e0a9-e50e24dcca9e"
BLE_METRICS_CHARACTERISTIC_UUID = "6e400002-b5a3-f393-e0a9-e50e24dcca9e"
BLE_COMMAND_CHARACTERISTIC_UUID = "6e400003-b5a3-f393-e0a9-e50e24dcca9e"
BLE_DEFAULT_DEVICE_NAME = "M5Monitor-Plus"


@dataclass(frozen=True)
class Config:
    # 串口路径。留空时，如果 auto_select_port 为 True，程序会尝试自动选择疑似 M5StickC Plus 的 USB 串口。
    port: str = ""

    # 串口波特率。必须和 ESP32 固件端 Serial.begin(...) 使用的波特率一致。
    baud_rate: int = 115200

    # 传输方式。serial 使用 USB 串口方案，ble 使用 BLE GATT 自定义服务。
    transport: str = "serial"

    # 指标发送间隔，单位毫秒。建议保持在 1000-2000ms，最小允许值为 500ms。
    interval_ms: int = 2000
    min_interval_ms: int = 500

    # 发送给 ESP32 的时区偏移，单位小时。默认 UTC+8，对应协议字段 Z:+8。
    timezone_offset_hours: int = 8
    min_timezone_offset_hours: int = -12
    max_timezone_offset_hours: int = 14

    # 是否在 port 为空时自动选择串口。设为 False 时必须手动填写 port 或通过 --port 指定。
    auto_select_port: bool = True

    # BLE 设备名。留空时按服务 UUID 或默认设备名自动发现；多台设备同时出现时建议指定。
    ble_name: str = ""

    # BLE 设备 ID 或地址。优先用于区分多台同名设备。
    ble_id: str = ""

    # 固件端默认广播的 BLE 设备名。
    ble_default_device_name: str = BLE_DEFAULT_DEVICE_NAME

    # 固件端广播的 BLE GATT 服务 UUID。当前使用 Nordic UART Service 形态的自定义服务。
    ble_service_uuid: str = BLE_SERVICE_UUID

    # 固件端用于写入指标协议文本的 BLE characteristic UUID。
    ble_metrics_characteristic_uuid: str = BLE_METRICS_CHARACTERISTIC_UUID

    # 固件端用于 notify 上报按键命令的 BLE characteristic UUID。
    ble_command_characteristic_uuid: str = BLE_COMMAND_CHARACTERISTIC_UUID

    # BLE 写入指标数据时使用的安全分片大小，默认 MTU 下保持 20 字节。
    ble_write_chunk_bytes: int = 20
    min_ble_write_chunk_bytes: int = 1

    # 是否连接后下发页面配置。关闭后 sender 仍需等待设备回传 OP-SYSINFO 才发送指标。
    pages_enabled: bool = True

    # 页面配置文件路径。相对路径以 sender 目录为基准。
    pages_config_path: str = "pages.json"

    # 非首页心跳间隔，单位毫秒。
    heartbeat_ms: int = 2000
    min_heartbeat_ms: int = 500

    # 页面数量和文本长度限制，需和固件侧保持一致。
    max_pages: int = 6
    max_page_text_length: int = 18

    # BLE 扫描超时时间，单位毫秒。
    ble_scan_timeout_ms: int = 8000
    min_ble_scan_timeout_ms: int = 1000

    # BLE 连接建立后等待 GATT discovery 的时间。过早 discovery 可能失败时可适当增加。
    ble_connect_delay_ms: int = 1000
    min_ble_connect_delay_ms: int = 0

    # BLE GATT discovery 单次超时时间，单位毫秒。
    ble_discovery_timeout_ms: int = 5000
    min_ble_discovery_timeout_ms: int = 1000

    # BLE GATT discovery 失败后的重试次数。
    ble_discovery_retries: int = 3
    min_ble_discovery_retries: int = 1

    # BLE discovery 失败后下一次尝试前的等待时间，单位毫秒。
    ble_discovery_retry_delay_ms: int = 500
    min_ble_discovery_retry_delay_ms: int = 0

    # 是否输出调试日志。开启后会打印每次写入串口或 BLE 的协议文本。
    verbose: bool = False
