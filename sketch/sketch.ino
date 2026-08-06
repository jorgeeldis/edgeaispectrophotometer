#include <Arduino_RouterBridge.h>
#include <SparkFun_AS7343.h>

// AS7343 Sensor Instance
SfeAS7343ArdI2C mySensor;

// Buffer used by the library to store all raw sensor channels
uint16_t myData[ksfAS7343NumChannels];

// Marker values sent to Python before and after the spectral data.
// These make it easier for the Python application to detect the
// beginning and end of a complete sample.
const float MARKER = 0.0001;

// Spectral channels that will be read from the AS7343
const sfe_as7343_channel_t channels[] = {
    CH_PURPLE_F1_405NM,
    CH_DARK_BLUE_F2_425NM,
    CH_BLUE_FZ_450NM,
    CH_LIGHT_BLUE_F3_475NM,
    CH_BLUE_F4_515NM,
    CH_GREEN_F5_550NM,
    CH_GREEN_FY_555NM,
    CH_ORANGE_FXL_600NM,
    CH_BROWN_F6_640NM,
    CH_RED_F7_690NM,
    CH_DARK_RED_F8_745NM,
    CH_NIR_855NM
};

// Human-readable names used when printing the readings
const char *channelNames[] = {
    "F1", "F2", "FZ", "F3", "F4", "F5",
    "FY", "FXL", "F6", "F7", "F8", "NIR"
};

// Stores the latest spectral measurements
float values[12];


// Stops program execution if a critical error occurs.
void halt(const char *message)
{
    Serial.println(message);
    Serial.println("Halting...");

    while (true)
        delay(1000);
}


// Arduino Setup
// Runs once during startup.
void setup()
{
    // Initialize Serial Monitor
    Serial.begin(9600);

    // Initialize I2C communication
    Wire.begin();

    // Initialize Arduino Router Bridge
    Bridge.begin();

    // Wait until the serial port is ready
    while (!Serial)
        delay(10);

    Serial.println("Initializing AS7343...");

    // Initialize the sensor
    if (!mySensor.begin())
        halt("Sensor failed to begin.");

    // Power on the sensor
    if (!mySensor.powerOn())
        halt("Failed to power on device.");

    // Configure the sensor to automatically read all spectral channels
    if (!mySensor.setAutoSmux(AUTOSMUX_18_CHANNELS))
        halt("Failed to configure AutoSmux.");

    // Set analog gain (4x)
    if (!mySensor.setAgain(AGAIN_4))
        halt("Failed to set gain.");

    // Enable spectral measurements
    if (!mySensor.enableSpectralMeasurement())
        halt("Failed to enable spectral measurement.");

    Serial.println("AS7343 ready.");
}


// Main Loop
// Continuously acquires spectral data and sends it to Python.
void loop()
{
    // Turn off the onboard LED before taking measurements
    mySensor.ledOff();

    // Trigger a new spectral acquisition
    if (!mySensor.readSpectraDataFromSensor())
    {
        Serial.println("Failed to read spectral data.");
        delay(2000);
        return;
    }

    // Retrieve all sensor registers
    mySensor.getData(myData);

    // Extract only the channels used by this application
    for (int i = 0; i < 12; i++)
    {
        values[i] = mySensor.getChannelData(channels[i]);
    }

    Serial.println("\n--- Spectral Readings ---");

    for (int i = 0; i < 12; i++)
    {
        Serial.print(channelNames[i]);
        Serial.print(": ");
        Serial.println(values[i]);
    }

    // -------------------------------------------------------------------------
    // Send data to the Python application through Arduino Router Bridge.
    //
    // Data Format:
    // MARKER,
    // F1, F2, FZ, F3, F4, F5,
    // FY, FXL, F6, F7, F8, NIR,
    // MARKER
    // -------------------------------------------------------------------------
    Bridge.notify(
        "record_sensor_samples",
        MARKER,
        values[0], values[1], values[2], values[3],
        values[4], values[5], values[6], values[7],
        values[8], values[9], values[10], values[11],
        MARKER);

    Serial.println("Sent to Python!");
    Serial.println("--------------------------------");

    // Wait before taking the next measurement
    delay(2000);
}