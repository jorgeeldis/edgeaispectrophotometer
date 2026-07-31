#include <Arduino_RouterBridge.h>
#include <SparkFun_AS7343.h>

SfeAS7343ArdI2C mySensor;

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

  // Set the GAIN to x4
  if (mySensor.setAgain(AGAIN_4) == false)
    {
        Serial.println("Failed to set gain.");
        Serial.println("Halting...");
        while (1)
            ;
    }
    Serial.println("Gain set to 512x.");

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
  mySensor.ledOff();

  // Read all data registers
  // if it fails, print a failure message and continue
  if (mySensor.readSpectraDataFromSensor() == false)
  {
    Serial.println("Failed to read spectral data.");
  }

  delay(2000);

  int channelsRead = mySensor.getData(myData);

  float begin = 0.0001;
  float F1 =  mySensor.getChannelData(CH_PURPLE_F1_405NM);
  float F2 =  mySensor.getChannelData(CH_DARK_BLUE_F2_425NM);
  float FZ =  mySensor.getChannelData(CH_BLUE_FZ_450NM);
  float F3 =  mySensor.getChannelData(CH_LIGHT_BLUE_F3_475NM);
  float F4 =  mySensor.getChannelData(CH_BLUE_F4_515NM);
  float F5 =  mySensor.getChannelData(CH_GREEN_F5_550NM);
  float FY =  mySensor.getChannelData(CH_GREEN_FY_555NM);
  float FXL =  mySensor.getChannelData(CH_ORANGE_FXL_600NM);
  float F6 =  mySensor.getChannelData(CH_BROWN_F6_640NM);
  float F7 =  mySensor.getChannelData(CH_RED_F7_690NM);
  float F8 =  mySensor.getChannelData(CH_DARK_RED_F8_745NM);
  float NIR =  mySensor.getChannelData(CH_NIR_855NM);
  float end = 0.0001;


  Serial.println("\n--- Spectral Readings ---");

  Serial.print("F1: ");
  Serial.println(F1);
  Serial.print("F2: ");
  Serial.println(F2);
  Serial.print("FZ: ");
  Serial.println(FZ);
  Serial.print("F3: ");
  Serial.println(F3);
  Serial.print("F4: ");
  Serial.println(F4);
  Serial.print("F5: ");
  Serial.println(F5);
  Serial.print("FY: ");
  Serial.println(FY);
  Serial.print("FXL: ");
  Serial.println(FXL);
  Serial.print("F6: ");
  Serial.println(F6);
  Serial.print("F7: ");
  Serial.println(F7);
  Serial.print("F8: ");
  Serial.println(F8);
  Serial.print("NIR: ");
  Serial.println(NIR);

  // Arduino MCU → Python MPU
  Bridge.notify(
      "record_sensor_samples",
      begin, F1, F2, FZ, F3, F4, F5,
      FY, FXL, F6, F7, F8, NIR, end);

  Serial.println("Sent to Python!");
  Serial.println("--------------------------------");
}