from arduino.app_utils import *
from arduino.app_bricks.web_ui import WebUI
import time

ui = WebUI()

def update_sensor_data():
    # Continuously get data from Bridge and send to HTML
    while True:
        try:
            channels = []
            for i in range(14):
                value = bridge.call(f"ch{i}")
                channels.append(str(value))
            
            # Send all 14 channels as comma-separated string
            data_string = ",".join(channels)
            
            # Emit to HTML via WebSocket
            ui.emit("html_sensor_event", data_string)
            
            time.sleep(1)  # Update every 1 second
        except Exception as e:
            print(f"Error: {e}")
            time.sleep(1)

# Start background thread
import threading
thread = threading.Thread(target=update_sensor_data, daemon=True)
thread.start()

App.run()