#pragma once

#include <Arduino.h>

namespace FirmwareConfig {
static const unsigned long SERIAL_BAUD_RATE = 115200;  // USB 串口接收 PC 指标数据的波特率。
static const uint32_t CPU_FREQUENCY_MHZ = 80;          // ESP32 CPU 频率，用于降低功耗。
static const char* const BLE_DEVICE_NAME = "M5Monitor-Plus";  // BLE 广播设备名称。
static const char* const BLE_SERVICE_UUID = "6e400001-b5a3-f393-e0a9-e50e24dcca9e";  // BLE UART 服务 UUID。
static const char* const BLE_METRICS_CHARACTERISTIC_UUID =
  "6e400002-b5a3-f393-e0a9-e50e24dcca9e";  // BLE 接收指标数据的特征 UUID。
static const uint16_t BLE_ADVERTISING_MIN_INTERVAL_UNITS = 800;   // BLE 最小广播间隔，单位为 0.625 ms。
static const uint16_t BLE_ADVERTISING_MAX_INTERVAL_UNITS = 1600;  // BLE 最大广播间隔，单位为 0.625 ms。
static const unsigned long DISCONNECT_TIMEOUT_MS = 5000;          // 超过该时间未收到指标数据后判定 PC 断开。
static const unsigned long BUTTON_LONG_PRESS_MS = 3000;           // 长按按钮进入设置页所需时长。
static const unsigned long LOOP_DELAY_MS = 20;                    // 屏幕唤醒时主循环延迟。
static const unsigned long SCREEN_SLEEP_LOOP_DELAY_MS = 200;      // 屏幕休眠时主循环延迟。
static const unsigned long CLOCK_REFRESH_INTERVAL_MS = 1000;      // 时钟文本刷新间隔。
static const unsigned long BATTERY_REFRESH_INTERVAL_MS = 5000;    // 电量百分比刷新间隔。
static const unsigned long EXTERNAL_POWER_REFRESH_INTERVAL_MS = 500;  // 外接电源状态检测刷新间隔。
static const unsigned long MAIN_DISPLAY_REFRESH_INTERVAL_MS = 250;    // 已连接指标页面的最小重绘间隔。
static const unsigned long DISCONNECTED_SCREEN_DIM_MS = 20000;        // 断连后进入暗屏前的等待时间。
static const unsigned long DISCONNECTED_SCREEN_SLEEP_MS = 60000;      // 断连后进入息屏前的等待时间。
static const uint8_t DISCONNECTED_SCREEN_DIM_BRIGHTNESS_INDEX = 0;    // 断连暗屏时使用的亮度档位索引。
static const int DEFAULT_TIMEZONE_OFFSET_HOURS = 8;  // PC 未下发时区前使用的默认时区偏移。
static const int MIN_TIMEZONE_OFFSET_HOURS = -12;    // 允许的最小时区偏移。
static const int MAX_TIMEZONE_OFFSET_HOURS = 14;     // 允许的最大时区偏移。
static const int SECONDS_PER_HOUR = 3600;            // 每小时秒数，用于时钟计算。
static const int SECONDS_PER_DAY = 86400;            // 每天秒数，用于时钟回绕。
static const size_t PROTOCOL_LINE_MAX_LENGTH = 1024; // 串口/BLE 单行 JSON Lines 协议的最大长度。
static const size_t BLE_NOTIFY_CHUNK_BYTES = 20;     // BLE notify 默认 MTU 下的安全分片大小。
static const uint8_t BLE_LINE_QUEUE_CAPACITY = 4;    // BLE 指标数据处理前可缓存的行数。
static const uint8_t MAX_CUSTOM_PAGES = 6;           // 电脑端可下发的自定义页面数量上限。
static const size_t MAX_PAGE_TEXT_LENGTH = 18;       // 页面标题、按钮文案和操作码的最大显示/保存长度。
static const unsigned long BUTTON_DOUBLE_CLICK_MS = 300;  // A 键双击识别窗口。

static const char* const BLE_COMMAND_CHARACTERISTIC_UUID =
  "6e400003-b5a3-f393-e0a9-e50e24dcca9e";  // BLE 上行 notify 命令特征 UUID。

static const uint8_t ORIENTATION_AXIS_X = 0;  // 方向检测使用的加速度计 X 轴枚举值。
static const uint8_t ORIENTATION_AXIS_Y = 1;  // 方向检测使用的加速度计 Y 轴枚举值。
static const uint8_t ORIENTATION_AXIS_Z = 2;  // 方向检测使用的加速度计 Z 轴枚举值。
static const uint8_t DISPLAY_ORIENTATION_PLANE_AXIS_1 = ORIENTATION_AXIS_X;  // 屏幕旋转检测使用的第一个加速度轴。
static const uint8_t DISPLAY_ORIENTATION_PLANE_AXIS_2 = ORIENTATION_AXIS_Y;  // 屏幕旋转检测使用的第二个加速度轴。
static const float DISPLAY_ORIENTATION_VECTOR_MIN_G = 0.35f;  // 触发方向检测所需的最小加速度向量强度。
static const float DISPLAY_ORIENTATION_DOT_THRESHOLD = 0.45f;  // 判断正向/倒置方向的点积阈值。
static const unsigned long ORIENTATION_SAMPLE_INTERVAL_MS = 80;  // 屏幕旋转检测的加速度采样间隔。
static const unsigned long ORIENTATION_STABLE_MS = 240;          // 方向保持稳定达到该时长后才旋转屏幕。

static const uint8_t DEFAULT_BRIGHTNESS_INDEX = 2;  // 默认亮度档位索引。
static const uint8_t BRIGHTNESS_LEVELS[] = { 20, 40, 60, 80, 100 };  // 屏幕亮度百分比预设。
static const size_t BRIGHTNESS_LEVEL_COUNT =
  sizeof(BRIGHTNESS_LEVELS) / sizeof(BRIGHTNESS_LEVELS[0]);  // 亮度档位数量。

static const float EXTERNAL_POWER_PRESENT_VOLTAGE = 4.40f;  // 判断 VBus/Vin 存在外接电源的电压阈值。
}
