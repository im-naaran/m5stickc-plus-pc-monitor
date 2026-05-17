#include "SerialReceiver.h"

void SerialReceiver::begin(unsigned long baudRate) {
  Serial.begin(baudRate);
  clear();
}

bool SerialReceiver::readLine(String& outLine) {
  while (Serial.available() > 0) {
    char ch = static_cast<char>(Serial.read());

    if (ch == '\r') {
      continue;
    }

    if (ch == '\n') {
      outLine = buffer;
      buffer = "";
      outLine.trim();
      return outLine.length() > 0;
    }

    buffer += ch;
    if (buffer.length() > FirmwareConfig::PROTOCOL_LINE_MAX_LENGTH) {
      clear();
      return false;
    }
  }

  return false;
}

void SerialReceiver::sendLine(const String& line) {
  Serial.print(line);
}

void SerialReceiver::clear() {
  buffer = "";
}
