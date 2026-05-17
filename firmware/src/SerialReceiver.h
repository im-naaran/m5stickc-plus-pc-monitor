#pragma once

#include <Arduino.h>
#include "FirmwareConfig.h"

class SerialReceiver {
public:
  void begin(unsigned long baudRate);
  bool readLine(String& outLine);
  void sendLine(const String& line);
  void clear();

private:
  String buffer;
};
