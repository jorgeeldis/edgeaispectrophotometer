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
    Wire.begin();       // Initialize I²C communication
    Bridge.begin(); 
}

void loop() {
  readSpectralData();
  
  // Update Bridge with fresh data every loop
  for (int i = 0; i < NUM_CHANNELS; i++) {
    String key = "ch" + String(i);
    Bridge.put(key, String(spectralData[i]));
  }
  
  delay(1000);
}
