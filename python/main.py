from arduino.app_utils import *
from arduino.app_bricks.web_ui import WebUI

ui = WebUI()

# Global variable to temporarily hold the latest data from the hardware
latest_hardware_data = []

@ui.sio.on('run_arduino_function')
async def handle_frontend_request(sid, data=None):
    print(f"Frontend requested hardware baseline scan...")
    
    # 1. Trigger the actual physical hardware scan. 
    # We call a function on the C++ side using Bridge.request or a standard global trigger
    # (Assuming your C++ side sends the array back to process_array)
    
    # 2. Emit the LATEST captured array data straight to the frontend.
    # Note: Send the array directly so your Javascript matches what Plotly expects!
    print(f"Action complete. Sending array data to frontend: {latest_hardware_data}")
    await ui.sio.emit('sendChannels', latest_hardware_data)

def loop():
    try:
        # Request the channel data string from the Arduino C++ sketch
        arduino_string = Bridge.call("sendChannels")
        print(f"Successfully retrieved channel data: {arduino_string}")
        
    except ValueError as e:
        # This catches error code (2) safely during board startup/reboots
        print("Waiting for Arduino hardware to register 'sendChannels' method...")
        
    except Exception as e:
        print(f"Unexpected connection error: {e}")

    # Wait 1 second before polling again to prevent system lag
    time.sleep(1)

App.run(user_loop=loop)
