// SPDX-FileCopyrightText: Copyright (C) Arduino s.r.l. and/or its affiliated companies
//
// SPDX-License-Identifier: MPL-2.0

#include <Arduino_RouterBridge.h>
#include <Wire.h>
#define AS7343_I2C_ADDR 0x39
#define NUM_CHANNELS 14
uint16_t spectralData[NUM_CHANNELS] = {0};

void readSpectralData() {
  Wire.beginTransmission(AS7343_I2C_ADDR);
  Wire.write(0x94); // Example: Register address for spectral data
  Wire.endTransmission();
  Wire.requestFrom(AS7343_I2C_ADDR, NUM_CHANNELS); // Request 14 bytes of spectral data

  if (Wire.available() == NUM_CHANNELS) {
    for (int i = 0; i < NUM_CHANNELS; i++) {
      spectralData[i] = Wire.read();  // Store each channel value
      Serial.print("Ch"); Serial.print(i); Serial.print(": ");
      Serial.println(spectralData[i]);
    }
  } else {
    Serial.print("ERROR: Expected 14 bytes, got ");
    Serial.println(Wire.available());
  }
}

void setup()
{
    Wire.begin();
    Bridge.begin();
    
    // Provide lambda functions that return current values
    Bridge.provide("ch0", []() { return String(spectralData[0]); });
    Bridge.provide("ch1", []() { return String(spectralData[1]); });
    Bridge.provide("ch2", []() { return String(spectralData[2]); });
    Bridge.provide("ch3", []() { return String(spectralData[3]); });
    Bridge.provide("ch4", []() { return String(spectralData[4]); });
    Bridge.provide("ch5", []() { return String(spectralData[5]); });
    Bridge.provide("ch6", []() { return String(spectralData[6]); });
    Bridge.provide("ch7", []() { return String(spectralData[7]); });
    Bridge.provide("ch8", []() { return String(spectralData[8]); });
    Bridge.provide("ch9", []() { return String(spectralData[9]); });
    Bridge.provide("ch10", []() { return String(spectralData[10]); });
    Bridge.provide("ch11", []() { return String(spectralData[11]); });
    Bridge.provide("ch12", []() { return String(spectralData[12]); });
    Bridge.provide("ch13", []() { return String(spectralData[13]); });
}

void loop() {
    readSpectralData();
    delay(1000);
}