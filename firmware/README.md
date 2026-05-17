# ESP32 Firmware

本目录是 M5StickC Plus 固件。固件通过 USB Serial 或 BLE GATT 与电脑端 sender 交换 JSON Lines 协议，维护设备状态，并刷新 LCD 显示。

## 设计思路

固件只负责设备侧逻辑：接收协议、解析字段、维护状态、显示 UI、处理按键和持久化设备设置。它不采集电脑指标，不负责电脑端串口选择，也不处理系统级蓝牙配对。

核心流程：

```text
setup:
  set CPU frequency
  initialize M5StickC Plus and IMU
  load persisted settings from NVS
  start USB Serial
  start BLE when enabled
  initialize LCD and draw boot screen

loop:
  update buttons and peripherals
  read complete lines from Serial and BLE
  parse JSON Lines protocol
  update AppState by existing fields
  refresh local clock, battery and power state
  handle connection timeout and screen power state
  send page subscription and button commands back to sender
  update orientation when enabled
  draw current view
```

`AppState` 是固件运行时的唯一共享状态。各模块围绕它分工：接收器只收集完整行，协议层只解析字段，显示层只绘制状态，`main.cpp` 负责流程编排和业务状态切换。

## 职责边界

负责：

- 初始化 M5StickC Plus、LCD、IMU、USB Serial 和 BLE。
- 通过 USB Serial 和 BLE characteristic 接收 JSON Lines 文本。
- 解析页面配置、CPU、内存、时间戳、时区和心跳消息。
- 维护连接状态、本地时间、电池估算、外接电源状态、亮度和设置页状态。
- 绘制启动页、主页面、自定义页面、断连页和设置页。
- 处理 A/B 按键交互，并把自定义页面操作码回传给 sender。
- 根据当前页面向 sender 发送 `OP-SYSINFO` / `OP-SYSINFO-STOP`，控制指标推送。
- 持久化亮度、BLE 开关和自动旋转开关。
- 执行轻量省电策略：断连降亮、断连熄屏、熄屏慢轮询、跳过绘制、暂停自动旋转采样、CPU 降频。

不负责：

- 采集电脑系统指标。
- 打开或选择电脑端串口。
- 管理电脑端命令行参数。
- 系统级蓝牙配对。
- 持久化指标值、连接状态、时间戳、时区或电池百分比。

## 数据协议

USB Serial 和 BLE 共用同一套应用协议。每条消息是一行 UTF-8 JSON 文本，以 `\n` 结尾。

页面配置：

```json
{"type":"pages.config","data":{"pages":[{"name":"clipboard","actions":[{"event":"a.click","label":"COPY","op":"OP-CP"},{"event":"a.double","label":"PASTE","op":"OP-PA"}]}]}}
```

带时间同步的指标：

```json
{"type":"metrics.update","data":{"cpu":25,"memory":60,"timestamp":1714440000,"timezone":"+8"}}
```

字段说明：

| 字段 | 含义 | 类型 | 范围 | 必填 |
| --- | --- | --- | --- | --- |
| `type` | 消息类型 | 字符串 | `pages.config`、`metrics.update`、`ping`、`device.command` | 是 |
| `data.cpu` | CPU 使用率 | 整数百分比 | `0-100` | `metrics.update` 中可选 |
| `data.memory` | 内存使用率 | 整数百分比 | `0-100` | `metrics.update` 中可选 |
| `data.timestamp` | Unix 时间戳 | 秒级整数 | `0-4294967295` | `metrics.update` 中可选 |
| `data.timezone` | 时区偏移 | 整数小时或字符串 | `-12` 到 `+14` | `metrics.update` 中可选 |
| `data.pages` | 自定义页面数组 | 数组 | 最多 6 页 | `pages.config` 必填 |
| `data.op` | 设备回传操作码 | 字符串 | 以 `OP-` 开头 | `device.command` 必填 |

解析规则：

- `metrics.update` 中 `cpu/memory/timestamp/timezone` 都是可选字段，存在且解析成功时才更新对应状态。
- `pages.config` 中每页需要 `name`，并且必须同时提供 `a.click` 和 `a.double` 两个 action。
- 页面标题、按钮文案和操作码会限制到 `MAX_PAGE_TEXT_LENGTH`。
- `ping` 只用于维持连接状态，不更新指标。
- 未知 JSON 类型和未知字段会被忽略。
- CPU/内存小于 `0` 按 `0`，大于 `100` 按 `100`。
- 时间戳只接受非负秒级 Unix 时间戳。
- 时区接受带符号或不带符号的整数小时偏移。
- 收到有效消息会设置 `connected = true` 并更新 `lastUpdateMs`。
- 超过 `DISCONNECT_TIMEOUT_MS` 没有收到有效消息后，状态变为 disconnected。

设备回传命令：

```json
{"type":"device.command","data":{"op":"OP-SYSINFO","source":"page0","page":0,"event":"page.enter"}}
```

首页进入时固件发送 `OP-SYSINFO`，离开首页或进入设置页时发送 `OP-SYSINFO-STOP`。自定义页面按 A 短按 / 双击时，固件发送页面配置中的操作码。

## 传输方式

### USB Serial

USB Serial 默认波特率为 `115200`。`SerialReceiver` 逐字节读取，忽略 `\r`，遇到 `\n` 返回一条完整协议行。单行长度超过 `PROTOCOL_LINE_MAX_LENGTH` 时会清空当前缓冲，避免异常输入占用内存。设备回传命令也通过同一串口写出 JSON Lines。

### BLE GATT

固件作为 BLE Peripheral，电脑端 sender 作为 Central。

| 项 | 值 |
| --- | --- |
| Device Name | `M5Monitor-Plus` |
| Service UUID | `6e400001-b5a3-f393-e0a9-e50e24dcca9e` |
| Metrics Characteristic UUID | `6e400002-b5a3-f393-e0a9-e50e24dcca9e` |
| Command Characteristic UUID | `6e400003-b5a3-f393-e0a9-e50e24dcca9e` |
| Metrics Properties | `Write`, `Write Without Response` |
| Command Properties | `Read`, `Notify` |
| Payload | UTF-8 JSON Lines 文本 |

`BleReceiver` 只负责 BLE 接入、完整行收集和命令 notify。BLE callback 中收到的数据会先按 `\n` 拆行，再放入短队列交给主循环处理。队列满时丢弃最旧行，保留较新的监控数据。设备回传 JSON Lines 时会按 `BLE_NOTIFY_CHUNK_BYTES` 分片 notify，sender 负责按换行重组。

设置页将 `ble` 设为 `off` 后，固件会停止 advertising、断开当前 BLE 客户端并清空 BLE 队列；USB Serial 仍然可用。

## 状态和显示

主页面显示 CPU、RAM、本地时间、电池状态和连接状态。收到时间戳后，固件以该时间戳和 `millis()` 建立本地时间基准，之后每秒刷新 `HH:MM` 文本。

自定义页面来自 sender 下发的 `pages.config`。B 短按在首页和自定义页面之间切换；在自定义页面中，A 短按 / 双击会把 action 的操作码通过 `device.command` 回传。

断连页在没有有效电脑数据时显示。若 BLE 已连接但没有收到有效协议行，会显示 BLE 链接和写入诊断计数，便于区分“蓝牙已连但协议不对”和“完全未连接”。

电池百分比由电池电压曲线估算，外接电源状态通过 VBus/Vin 电压判断。短时间电量跳动不一定代表真实容量快速下降。

显示层会跳过重复绘制，并对已连接主页面做最小刷新间隔限制，减少 LCD 刷新和功耗。

## 按键和设置

正常页面：

- 长按 B 满 `BUTTON_LONG_PRESS_MS` 进入设置页。
- B 短按：切换首页和自定义页面。
- 自定义页面 A 短按：回传当前页面的 `a.click` 操作码。
- 自定义页面 A 双击：回传当前页面的 `a.double` 操作码。
- 断连熄屏后，按 A 或 B 唤醒屏幕。
- USB Serial 或 BLE 收到有效数据后也会唤醒屏幕。

设置页：

- B 短按：选择下一个设置项。
- A 短按：修改当前设置项。
- 选中 `exit` 后 A 短按：退出设置页。

设置项顺序：

| 设置项 | 行为 |
| --- | --- |
| `battery` | 只读，显示电量估算值 |
| `brightness` | 在 5 档亮度间循环 |
| `ble` | 启停 BLE |
| `rotate` | 开关自动旋转 |
| `exit` | 退出设置页 |

持久化字段：

| 状态字段 | NVS key | 默认值 |
| --- | --- | --- |
| `brightnessIndex` | `bright` | `2` |
| `bleEnabled` | `ble` | `true` |
| `autoRotateEnabled` | `rotate` | `true` |

NVS namespace 为 `m5mon`，schema key 为 `schema`，当前版本为 `1`。读取到未来版本 schema 时会清空该 namespace 并恢复默认值。

## 省电策略

当前固件使用轻量省电策略，不进入 ESP32 light sleep 或 deep sleep。

- 启动时调用 `setCpuFrequencyMhz(80)`。
- 断连超过 `DISCONNECTED_SCREEN_DIM_MS` 后降到最低亮度。
- 断连超过 `DISCONNECTED_SCREEN_SLEEP_MS` 后关闭 LCD 背光。
- 熄屏后 loop delay 从 `20ms` 增加到 `200ms`。
- 熄屏时跳过绘制和自动旋转采样，但继续处理 USB/BLE/button。
- `rotate off` 时跳过 IMU 加速度采样。
- `ble off` 时停止 BLE advertising，并断开 BLE 客户端。

断连熄屏状态：

```text
connected or settings open:
  screen on
  configured brightness
  normal loop delay

disconnected + screen on:
  draw disconnected page
  dim after 20s
  sleep after 60s

disconnected + screen sleeping:
  LCD backlight off
  skip draw and orientation sampling
  slow loop delay

button input or valid metric input:
  wake screen
  restore configured brightness
```

## 目录和模块

```text
firmware/
├── platformio.ini
├── README.md
└── src/
    ├── main.cpp
    ├── AppState.h
    ├── FirmwareConfig.h
    ├── Protocol.h / Protocol.cpp
    ├── SerialReceiver.h / SerialReceiver.cpp
    ├── BleReceiver.h / BleReceiver.cpp
    ├── DisplayView.h / DisplayView.cpp
    └── SettingsStore.h / SettingsStore.cpp
```

模块职责：

| 模块 | 职责 |
| --- | --- |
| `main.cpp` | 初始化、主循环、状态切换、按键、屏幕电源、时间和电池刷新 |
| `AppState.h` | 定义运行时共享状态和设置项枚举 |
| `FirmwareConfig.h` | 集中维护固件运行参数和协议常量 |
| `Protocol` | 解析协议行，输出字段存在标记和值 |
| `SerialReceiver` | 从 USB Serial 收集完整协议行 |
| `BleReceiver` | 初始化 BLE GATT，收集 BLE 写入的完整协议行 |
| `DisplayView` | 绘制 LCD 页面，控制亮度、背光和旋转 |
| `SettingsStore` | 使用 ESP32 NVS 读写持久化设置 |

## 关键配置

`src/FirmwareConfig.h` 集中维护运行参数：

| 配置 | 当前值 | 含义 |
| --- | ---: | --- |
| `SERIAL_BAUD_RATE` | `115200` | USB Serial 波特率 |
| `CPU_FREQUENCY_MHZ` | `80` | ESP32 CPU 频率 |
| `DISCONNECT_TIMEOUT_MS` | `5000` | 连接超时时间 |
| `BUTTON_LONG_PRESS_MS` | `3000` | B 键进入设置页的长按时间 |
| `LOOP_DELAY_MS` | `20` | 正常 loop 延迟 |
| `SCREEN_SLEEP_LOOP_DELAY_MS` | `200` | 熄屏后的 loop 延迟 |
| `CLOCK_REFRESH_INTERVAL_MS` | `1000` | 本地时钟刷新间隔 |
| `BATTERY_REFRESH_INTERVAL_MS` | `5000` | 电池读取间隔 |
| `EXTERNAL_POWER_REFRESH_INTERVAL_MS` | `500` | 外接电源检测间隔 |
| `MAIN_DISPLAY_REFRESH_INTERVAL_MS` | `250` | 主页面最小重绘间隔 |
| `DISCONNECTED_SCREEN_DIM_MS` | `20000` | 断连后降亮等待时间 |
| `DISCONNECTED_SCREEN_SLEEP_MS` | `60000` | 断连后熄屏等待时间 |
| `DISCONNECTED_SCREEN_DIM_BRIGHTNESS_INDEX` | `0` | 断连降亮使用的亮度档位索引 |
| `BUTTON_DOUBLE_CLICK_MS` | `300` | A 键双击识别窗口 |
| `DEFAULT_TIMEZONE_OFFSET_HOURS` | `8` | 默认时区偏移 |
| `BRIGHTNESS_LEVELS` | `20, 40, 60, 80, 100` | 亮度档位 |
| `ORIENTATION_SAMPLE_INTERVAL_MS` | `80` | 自动旋转采样间隔 |
| `ORIENTATION_STABLE_MS` | `240` | 方向稳定后才旋转的等待时间 |
| `BLE_ADVERTISING_MIN_INTERVAL_UNITS` | `800` | BLE 广播最小间隔，单位 0.625ms |
| `BLE_ADVERTISING_MAX_INTERVAL_UNITS` | `1600` | BLE 广播最大间隔，单位 0.625ms |
| `PROTOCOL_LINE_MAX_LENGTH` | `1024` | 单行协议最大长度 |
| `BLE_NOTIFY_CHUNK_BYTES` | `20` | BLE notify 分片大小 |
| `BLE_LINE_QUEUE_CAPACITY` | `4` | BLE 完整行队列容量 |

## 执行和部署

本目录使用 PlatformIO 构建。构建环境在 `platformio.ini` 中定义：

| 项 | 值 |
| --- | --- |
| env | `m5stick-c-plus` |
| platform | `espressif32` |
| board | `m5stick-c` |
| framework | `arduino` |
| monitor_speed | `115200` |
| lib_deps | `m5stack/M5StickCPlus` |

编译：

```bash
cd firmware
pio run
```

上传固件：

```bash
pio run -t upload
```

指定上传端口：

```bash
pio run -t upload --upload-port /dev/tty.usbserial-xxxx
```

打开串口监视器：

```bash
pio device monitor
```

恢复默认设备设置：

```bash
pio run -t erase
pio run -t upload
```

部署注意事项：

- 上传前关闭 sender、Arduino Serial Monitor、M5Burner、`screen`、`minicom` 等占用串口的程序。
- 普通 `pio run -t upload` 不会清除 NVS，亮度、BLE 和自动旋转设置会保留。
- 如果 BLE 被设置为 `off`，需要在设备设置页重新打开，或执行 erase 后重新上传恢复默认。
- 协议字段变更时，需要同步更新 sender 的编码逻辑和本文档。
