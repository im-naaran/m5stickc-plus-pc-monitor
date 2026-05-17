# M5StickC Plus PC Monitor

使用 M5StickC Plus 作为电脑状态监控小屏，通过 USB 串口或 BLE GATT 显示 CPU 使用率、内存使用率、连接状态、电脑本地时间，并支持电脑端下发的自定义页面和按键命令回传。

## 功能概览

- USB Serial 通信，默认波特率 `115200`。
- BLE GATT 自定义服务通信，电脑端作为 Central，M5StickC Plus 作为 Peripheral。
- 当前 sender 与固件使用 JSON Lines 双向协议。
- 显示 CPU、RAM、PC 连接状态和 `HH:MM` 时间。
- 支持电脑端下发自定义页面，A 键短按 / 双击触发不同操作码并回传给 sender 执行。
- 首页显示系统指标，切到自定义页面时 sender 暂停指标推送并只发送心跳。
- 长按 B 满 3 秒进入设置页，设置页支持滚动列表。
- 设置页可调整亮度、查看电量、开关 BLE、开关自动旋转。
- 显示 `Disconnected` 后 20 秒降到最低亮度，60 秒关闭屏幕背光，按 A/B 任意键唤醒。
- 屏幕熄灭后暂停绘制和自动旋转采样，并降低主循环频率。
- 固件默认将 ESP32 CPU 频率设为 `80MHz`。

## 项目结构

```text
firmware/   M5StickC Plus 固件，PlatformIO + Arduino C++
sender/     电脑端 Python 服务，采集指标并写入 USB Serial 或 BLE
```

详细说明：

- [ESP32 Firmware](firmware/README.md)
- [Python Sender](sender/README.md)

## 快速开始

### 1. 刷写固件

先停止 sender 或其他串口监视器，避免串口被占用。

```bash
cd firmware
pio run -t upload
```

如果需要指定设备端口：

```bash
cd firmware
pio run -t upload --upload-port /dev/tty.usbserial-xxxx
```

不知道串口名时可以先列出端口：

```bash
cd sender
uv sync
uv run python main.py --list-ports
```

### 2. 启动 USB 发送端

```bash
cd sender
uv sync
uv run python main.py
```

如果自动选择失败，先列出串口，再指定端口：

```bash
uv run python main.py --list-ports
uv run python main.py --port /dev/tty.usbserial-xxxx
```

### 3. 启动 BLE 发送端

先确认固件设置页中的 `ble` 为 `on`。

```bash
cd sender
uv sync
uv run python main.py --transport ble
```

多台设备同时存在时，先列出设备，再指定设备名或 ID：

```bash
uv run python main.py --list-ble
uv run python main.py --transport ble --ble-name M5Monitor-Plus
```

更多 sender 参数见 [sender/README.md](sender/README.md)。

### 4. 开机运行

固件显示 `Waiting for PC` 后，启动 sender 即可下发页面配置，并在首页显示 CPU、RAM、本地时间和连接状态。USB Serial 和 BLE 使用同一套应用协议，任选其一运行即可。

## 设备操作

正常页面：

- 长按 B 满 3 秒：进入设置页。
- 短按 B：在首页和电脑端下发的自定义页面之间切换。
- 自定义页面中短按 A / 双击 A：向 sender 回传页面配置里的操作码。
- USB 或 BLE 收到有效数据后显示 `PC Connected`。
- 超过 5 秒未收到有效数据后显示 `Disconnected`。
- 显示 `Disconnected` 后 20 秒先降到最低亮度，60 秒后屏幕背光关闭；按 A 或 B 唤醒。

设置页：

- 短按 B：移动到下一个设置项。
- 短按 A：修改当前设置项。
- 选中 `exit` 后短按 A：退出设置页。
- 设置项超过屏幕高度时会自动滚动，右上角显示当前位置，例如 `3/5`。

当前设置项：

| 设置项 | 取值 | 说明 |
| --- | --- | --- |
| `battery` | 百分比或 `--` | 当前电池电量估算值，只读 |
| `brightness` | `1/5` 到 `5/5` | 屏幕亮度，依次对应 `20, 40, 60, 80, 100`，默认第 3 档 |
| `ble` | `on/off` | BLE 开关，默认 `on` |
| `rotate` | `on/off` | 自动旋转开关，默认 `on` |
| `exit` | - | 短按 A 退出设置页 |

说明：

- 设置页顺序为 `battery`、`brightness`、`ble`、`rotate`、`exit`。
- `brightness`、`ble` 和 `rotate` 会保存到 ESP32 NVS，重启和普通固件上传后仍会保留。
- `battery` 是按电池电压估算的百分比，短时间跳动不一定代表真实容量快速下降。
- `ble off` 后固件不会初始化 BLE，无法通过 BLE 连接设备，但 USB Serial 仍可使用；需要在设置页重新打开 BLE 才能用 BLE。
- `rotate off` 后不会继续采样 IMU，屏幕保持当前方向。

## 实现说明

USB Serial 和 BLE 使用同一套 JSON Lines 应用协议，BLE 不走系统级蓝牙配对。协议、BLE GATT、模块职责和配置参数的细节见：

- [firmware/README.md](firmware/README.md)
- [sender/README.md](sender/README.md)

## 常见问题

### 串口上传失败

确认 sender、串口监视器或其他占用串口的程序已经停止，然后重新执行上传命令。

### 恢复默认设备设置

`brightness`、`ble` 和 `rotate` 保存在 ESP32 NVS 中，普通 `pio run -t upload` 不会自动清除。开发时如需彻底清除设备端保存设置，可以执行：

```bash
cd firmware
pio run -t erase
pio run -t upload
```

### BLE 找不到设备

确认设置页 `ble` 为 `on`。如果屏幕已经熄灭，可以按 A/B 唤醒后重新执行：

```bash
cd sender
uv run python main.py --list-ble
```

### macOS BLE 权限

macOS 使用 BLE 时，需要给运行命令的程序开启蓝牙权限，例如 Terminal、iTerm、VS Code 或 wrap.app。

### 电量显示下降很快

电量百分比是电压估算值。屏幕背光、BLE、CPU 负载都会影响瞬时电压，短时间看到百分比跳动不一定等同于真实电池容量线性下降。
