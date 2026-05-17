#include "Protocol.h"

#include <ArduinoJson.h>

static int clampPercent(int value) {
  if (value < 0) {
    return 0;
  }

  if (value > 100) {
    return 100;
  }

  return value;
}

static bool parseInteger(const String& value, int& outValue) {
  String normalized = value;
  normalized.trim();

  if (normalized.length() == 0) {
    return false;
  }

  int start = 0;
  if (normalized.charAt(0) == '-' || normalized.charAt(0) == '+') {
    if (normalized.length() == 1) {
      return false;
    }
    start = 1;
  }

  for (int i = start; i < normalized.length(); ++i) {
    if (!isDigit(normalized.charAt(i))) {
      return false;
    }
  }

  outValue = normalized.toInt();
  return true;
}

static bool parseTimezoneOffsetHours(const String& value, int& outValue) {
  int parsedValue = 0;
  if (!parseInteger(value, parsedValue)) {
    return false;
  }

  if (parsedValue < FirmwareConfig::MIN_TIMEZONE_OFFSET_HOURS ||
      parsedValue > FirmwareConfig::MAX_TIMEZONE_OFFSET_HOURS) {
    return false;
  }

  outValue = parsedValue;
  return true;
}

static String limitedString(const char* value) {
  String normalized = value ? String(value) : String("");
  normalized.trim();
  if (normalized.length() > FirmwareConfig::MAX_PAGE_TEXT_LENGTH) {
    normalized = normalized.substring(0, FirmwareConfig::MAX_PAGE_TEXT_LENGTH);
  }
  return normalized;
}

static bool parseJsonMetrics(JsonObject data, ParseResult& result) {
  if (data["cpu"].is<int>()) {
    result.metrics.cpuPercent = clampPercent(data["cpu"].as<int>());
    result.hasCpu = true;
  }

  if (data["memory"].is<int>()) {
    result.metrics.memoryPercent = clampPercent(data["memory"].as<int>());
    result.hasMemory = true;
  }

  if (data["timestamp"].is<uint32_t>()) {
    result.timestampSeconds = data["timestamp"].as<uint32_t>();
    result.hasTimestamp = true;
  }

  if (data["timezone"].is<const char*>()) {
    int timezoneOffsetHours = 0;
    if (parseTimezoneOffsetHours(data["timezone"].as<const char*>(), timezoneOffsetHours)) {
      result.timezoneOffsetHours = timezoneOffsetHours;
      result.hasTimezone = true;
    }
  } else if (data["timezone"].is<int>()) {
    int timezoneOffsetHours = data["timezone"].as<int>();
    if (timezoneOffsetHours >= FirmwareConfig::MIN_TIMEZONE_OFFSET_HOURS &&
        timezoneOffsetHours <= FirmwareConfig::MAX_TIMEZONE_OFFSET_HOURS) {
      result.timezoneOffsetHours = timezoneOffsetHours;
      result.hasTimezone = true;
    }
  }

  return result.hasCpu || result.hasMemory || result.hasTimestamp || result.hasTimezone;
}

static bool readPageAction(JsonArray actions, const char* event, PageAction& action) {
  for (JsonObject item : actions) {
    const char* actionEvent = item["event"] | "";
    if (String(actionEvent) != event) {
      continue;
    }

    const char* label = item["label"] | "";
    const char* op = item["op"] | "";
    if (label[0] == '\0' || op[0] == '\0') {
      return false;
    }

    String opText = limitedString(op);
    if (!opText.startsWith("OP-")) {
      return false;
    }

    action.label = limitedString(label);
    action.op = opText;
    return action.label.length() > 0 && action.op.length() > 0;
  }

  return false;
}

static bool parsePagesConfig(JsonObject data, ParseResult& result) {
  JsonArray pages = data["pages"].as<JsonArray>();
  if (pages.isNull()) {
    return false;
  }

  uint8_t count = 0;
  for (JsonObject page : pages) {
    if (count >= FirmwareConfig::MAX_CUSTOM_PAGES) {
      break;
    }

    const char* name = page["name"] | "";
    JsonArray actions = page["actions"].as<JsonArray>();
    if (name[0] == '\0' || actions.isNull()) {
      continue;
    }

    CustomPage parsedPage;
    parsedPage.name = limitedString(name);
    if (!readPageAction(actions, "a.click", parsedPage.single) ||
        !readPageAction(actions, "a.double", parsedPage.doubleClick)) {
      continue;
    }

    result.pages[count] = parsedPage;
    count++;
  }

  result.pageCount = count;
  result.hasPagesConfig = true;
  return true;
}

static bool parseJsonLine(const String& normalized, ParseResult& result) {
  JsonDocument document;
  DeserializationError error = deserializeJson(document, normalized);
  if (error) {
    return false;
  }

  const char* type = document["type"] | "";
  if (String(type) == "ping") {
    result.ok = true;
    return true;
  }

  JsonObject data = document["data"].as<JsonObject>();
  if (String(type) == "metrics.update") {
    result.ok = parseJsonMetrics(data, result);
    return result.ok;
  }

  if (String(type) == "pages.config") {
    result.ok = parsePagesConfig(data, result);
    return result.ok;
  }

  return false;
}

ParseResult parseProtocolLine(const String& line) {
  ParseResult result;
  String normalized = line;
  normalized.trim();

  if (normalized.startsWith("{")) {
    parseJsonLine(normalized, result);
  }

  return result;
}

String encodeDeviceCommand(const String& op, const char* source, uint8_t page, const char* event) {
  JsonDocument document;
  document["type"] = "device.command";
  JsonObject data = document["data"].to<JsonObject>();
  data["op"] = op;
  data["source"] = source;
  data["page"] = page;
  data["event"] = event;

  String line;
  serializeJson(document, line);
  line += "\n";
  return line;
}
