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

  uint16_t data[12] = {
      readings[AS7343_CHANNEL_F1],
      readings[AS7343_CHANNEL_F2],
      readings[AS7343_CHANNEL_FZ],
      readings[AS7343_CHANNEL_F3],
      readings[AS7343_CHANNEL_F4],
      readings[AS7343_CHANNEL_F5],
      readings[AS7343_CHANNEL_FY],
      readings[AS7343_CHANNEL_FXL],
      readings[AS7343_CHANNEL_F6],
      readings[AS7343_CHANNEL_F7],
      readings[AS7343_CHANNEL_F8],
      readings[AS7343_CHANNEL_NIR]
  };

  // Arduino C++ → Python
  Bridge.notify("sendChannels", data);

  Serial.println("Sent spectrum to Python.");

  delay(2000);
}