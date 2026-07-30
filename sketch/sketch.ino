#include <Adafruit_AS7343.h>
#include <Arduino_RouterBridge.h>
#include <SparkFun_AS7343.h>

SfeAS7343ArdI2C mySensor;
Adafruit_AS7343 as7343;

uint16_t myData[ksfAS7343NumChannels]; // Array to hold spectral data

void setup()
{
  Serial.begin(9600);
  Wire.begin();
  Bridge.begin();

  while (!Serial)
    delay(10);

  Serial.println("Initializing AS7343...");

  // Initialize sensor and run default setup.
    if (mySensor.begin() == false)
    {
        Serial.println("Sensor failed to begin. Please check your wiring!");
        Serial.println("Halting...");
        while (1)
            ;
    }

    Serial.println("Sensor began.");

    // Power on the device
    if (mySensor.powerOn() == false)
    {
        Serial.println("Failed to power on the device.");
        Serial.println("Halting...");
        while (1)
            ;
    }
    Serial.println("Device powered on.");

    // Set the AutoSmux to output all 18 channels
    if (mySensor.setAutoSmux(AUTOSMUX_18_CHANNELS) == false)
    {
        Serial.println("Failed to set AutoSmux.");
        Serial.println("Halting...");
        while (1)
            ;
    }
    Serial.println("AutoSmux set to 18 channels.");

    // Enable Spectral Measurement
    if (mySensor.enableSpectralMeasurement() == false)
    {
        Serial.println("Failed to enable spectral measurement.");
        Serial.println("Halting...");
        while (1)
            ;
    }
    Serial.println("Spectral measurement enabled.");
}

void loop()
{
  mySensor.ledOn();
  delay(100);

  // Read all data registers
  // if it fails, print a failure message and continue
  if (mySensor.readSpectraDataFromSensor() == false)
  {
      Serial.println("Failed to read spectral data.");
  }

  mySensor.ledOff();
  int channelsRead = mySensor.getData(myData);

  float F1  = myData[0];
  float F2  = myData[1];
  float FZ  = myData[2];
  float F3  = myData[3];
  float F4  = myData[4];
  float F5  = myData[5];
  float FY  = myData[6];
  float FXL = myData[7];
  float F6  = myData[8];
  float F7  = myData[9];
  float F8  = myData[10];
  float NIR = myData[11];

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

  delay(100);
}