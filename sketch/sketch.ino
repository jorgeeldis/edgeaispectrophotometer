#include <Adafruit_AS7343.h>
#include <Arduino_RouterBridge.h>

Adafruit_AS7343 as7343;
uint16_t readings[AS7343_NUM_CHANNELS];   // size from the library, not a guess
unsigned long lastScan = 0;
const unsigned long SCAN_INTERVAL = 2000;

void setup() {
  Serial.begin(9600);
  Bridge.begin();
  // no while(!Serial) — it hangs when nothing is attached

  if (!as7343.begin()) {
    Serial.println("Error: AS7343 not found");
    while (1) { Bridge.update(); delay(10); }   // keep bridge alive even on failure
  }

  as7343.setGain(AS7343_GAIN_4X);
  as7343.setATIME(19);
  as7343.setASTEP(99);
}

void loop() {
  Bridge.update();                              // serviced every iteration

  if (millis() - lastScan < SCAN_INTERVAL) return;
  lastScan = millis();

  as7343.startMeasurement();
  while (!as7343.dataReady()) {
    Bridge.update();
    delay(1);
  }
  as7343.readAllChannels(readings);

  const uint8_t order[12] = {
    AS7343_CHANNEL_F1,  AS7343_CHANNEL_F2,  AS7343_CHANNEL_FZ,
    AS7343_CHANNEL_F3,  AS7343_CHANNEL_F4,  AS7343_CHANNEL_F5,
    AS7343_CHANNEL_FY,  AS7343_CHANNEL_FXL, AS7343_CHANNEL_F6,
    AS7343_CHANNEL_F7,  AS7343_CHANNEL_F8,  AS7343_CHANNEL_NIR
  };

  // Serialize to CSV — one string crosses the bridge cleanly
  String payload = "";
  for (int i = 0; i < 12; i++) {
    payload += String(readings[order[i]]);
    if (i < 11) payload += ",";
  }

  Serial.println(payload);
  Bridge.notify("sendChannels", payload);       // send the data, not "1"
}