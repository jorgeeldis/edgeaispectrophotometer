// SPDX-FileCopyrightText: Copyright (C) Arduino s.r.l. and/or its affiliated companies
//
// SPDX-License-Identifier: MPL-2.0

#include <Arduino_RouterBridge.h>
#include <Wire.h>
#define AS7343_I2C_ADDR 0x39


void readSpectralData() {
  Wire.beginTransmission(AS7343_I2C_ADDR);
  Wire.write(0x94); // Example: Register address for spectral data
  Wire.endTransmission();

  Wire.requestFrom(AS7343_I2C_ADDR, 14); // Request 14 bytes of spectral data
  if (Wire.available() == 14) {
    Serial.println("Spectral Data:");
    for (int i = 0; i < 14; i++) {
      uint8_t data = Wire.read();
      Serial.print("Channel ");
      Serial.print(i + 1);
      Serial.print(": ");
      Serial.println(data);
    }
  } else {
    Serial.println("Failed to read spectral data.");
  }
}

void setup()
{
    Wire.begin();       // Initialize I²C communication
    Bridge.begin();
    Bridge.provide("data", data);  
}

void loop() {
  // Read and print spectral data
  readSpectralData();
  delay(1000); // Wait 1 second before the next reading
}
