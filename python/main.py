from arduino.app_utils import *
from arduino.app_bricks.web_ui import WebUI
import json

ui = WebUI()

@ui.on("captureBaseline")
def handle_web_click(data):
    # Sends an empty string trigger or payload to MCU
    Bridge.notify("getBaseline", "")

# Fix: Decode the incoming JSON-string array from the C++ sketch before broadcasting to WebUI
def forward_baseline(payload):
    try:
        data_list = json.loads(payload)
        ui.send_message("updateBaseline", data_list)
    except Exception as e:
        print("Error parsing baseline data array:", e)

Bridge.provide("baselineData", forward_baseline)

if __name__ == "__main__":
    App.run()
