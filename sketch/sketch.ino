#include <Adafruit_AS7343.h>

Adafruit_AS7343 as7343;

void setup() {
  Serial.begin(9600);
  while (!Serial) delay(10); // Wait for Serial Monitor to open

  Serial.println("Initializing AS7343...");

  if (!as7343.begin()) {
    Serial.println("Error: Could not find AS7343 sensor! Check wiring.");
    while (1) delay(10);
  }

  // Balanced configurations to prevent saturation on bright 5000K LEDs
  as7343.setGain(AS7343_GAIN_4X);
  as7343.setATIME(19);
  as7343.setASTEP(99);
  
  // Optional: Uncomment the line below if you are using the onboard illumination LED
  // as7343.enableLed(true);

  Serial.println("AS7343 successfully initialized!");
  Serial.println("---------------------------------------------------------");
}

void loop() {
  uint16_t readings[14]; // Array to hold all channel data
  
  // Start the hardware spectral conversion
  as7343.startMeasurement();
  
  // Wait until data is fully processed by the internal ADC
  while (!as7343.dataReady()) {
    delay(1);
  }
  
  // Read all 14 channels into our array
  as7343.readAllChannels(readings);

  // Print spectral channels (wavelength order)
  Serial.println("\n--- Spectral Readings ---");

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

  Serial.println(data);

  Serial.println("---------------------------------------------------------");

  delay(2000); // Wait 2 seconds before the next reading loop
}
