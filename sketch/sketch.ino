#include <ArduinoRouterBridge.h> // Core App Lab Linux-MCU communication library

const int SENSOR_PIN = A0;
int lastValue = 0;

void setup() {
  RouterBridge.begin(); // Establishes communication with the MPU Linux layer
  pinMode(SENSOR_PIN, INPUT);
}

void loop() {
  int currentValue = analogRead(SENSOR_PIN);
  
  // If sensor data shifts significantly, alert the Python script
  if (abs(currentValue - lastValue) > 50) {
    lastValue = currentValue;
    
    // Broadcast key value pair to the Python event listener
    RouterBridge.sendInt("raw_sensor_event", 2);
  }
  
  delay(200); // Polling stability pause
}
