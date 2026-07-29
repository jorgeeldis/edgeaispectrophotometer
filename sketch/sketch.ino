#include <Adafruit_AS7343.h>
#include <Arduino_RouterBridge.h>

Adafruit_AS7343 as7343;

void setup()
{
  Serial.begin(9600);
  Bridge.begin();

  while (!Serial)
    delay(10);

  Serial.println("Initializing AS7343...");

  if (!as7343.begin())
  {
    Serial.println("Error: Could not find AS7343 sensor!");

    while (1)
      delay(10);
  }

  as7343.setGain(AS7343_GAIN_4X);
  as7343.setATIME(19);
  as7343.setASTEP(99);

  Serial.println("AS7343 successfully initialized!");
}

void loop()
{
  uint16_t readings[14];

  as7343.startMeasurement();

  while (!as7343.dataReady())
  {
    delay(1);
  }

  as7343.readAllChannels(readings);

  float F1  = readings[AS7343_CHANNEL_F1];
  float F2  = readings[AS7343_CHANNEL_F2];
  float FZ  = readings[AS7343_CHANNEL_FZ];
  float F3  = readings[AS7343_CHANNEL_F3];
  float F4  = readings[AS7343_CHANNEL_F4];
  float F5  = readings[AS7343_CHANNEL_F5];
  float FY  = readings[AS7343_CHANNEL_FY];
  float FXL = readings[AS7343_CHANNEL_FXL];
  float F6  = readings[AS7343_CHANNEL_F6];
  float F7  = readings[AS7343_CHANNEL_F7];
  float F8  = readings[AS7343_CHANNEL_F8];
  float NIR = readings[AS7343_CHANNEL_NIR];

  Serial.println("\n--- Spectral Readings ---");

  Serial.print("F1: ");  Serial.println(F1);
  Serial.print("F2: ");  Serial.println(F2);
  Serial.print("FZ: ");  Serial.println(FZ);
  Serial.print("F3: ");  Serial.println(F3);
  Serial.print("F4: ");  Serial.println(F4);
  Serial.print("F5: ");  Serial.println(F5);
  Serial.print("FY: ");  Serial.println(FY);
  Serial.print("FXL: "); Serial.println(FXL);
  Serial.print("F6: ");  Serial.println(F6);
  Serial.print("F7: ");  Serial.println(F7);
  Serial.print("F8: ");  Serial.println(F8);
  Serial.print("NIR: "); Serial.println(NIR);

  // Arduino MCU → Python MPU
  Bridge.notify(
    "record_sensor_samples",
    F1, F2, FZ, F3, F4, F5,
    FY, FXL, F6, F7, F8, NIR
  );

  Serial.println("Sent to Python!");
  Serial.println("--------------------------------");

  delay(2000);
}