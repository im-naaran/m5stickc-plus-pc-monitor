#pragma once

#include <Arduino.h>
#include "AppState.h"

struct ParseResult {
  bool ok = false;
  bool hasPagesConfig = false;
  MetricsState metrics;
  bool hasCpu = false;
  bool hasMemory = false;
  bool hasTimestamp = false;
  uint32_t timestampSeconds = 0;
  bool hasTimezone = false;
  int timezoneOffsetHours = FirmwareConfig::DEFAULT_TIMEZONE_OFFSET_HOURS;
  CustomPage pages[FirmwareConfig::MAX_CUSTOM_PAGES];
  uint8_t pageCount = 0;
};

ParseResult parseProtocolLine(const String& line);
String encodeDeviceCommand(const String& op, const char* source, uint8_t page, const char* event);
int clampPercent(int value);
