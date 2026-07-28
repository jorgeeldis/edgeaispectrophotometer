from arduino.app_utils import *
from arduino.app_bricks.web_ui import WebUI
import json

ui = WebUI()

def handle_alert(payload):
    print(f"[Python Received] Notification: {payload}")

def main():
    # 2. Initialize the Python bridge instance
    
    Bridge.begin()

    # 3. Link the C++ notification name to your Python function
    Bridge.provide("sendChannels", handle_alert)
    print("Python Bridge is active. Waiting for notifications...")

    # 4. Keep the script alive to listen for events
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("Stopping Python Bridge.")

if __name__ == "__main__":
    main()