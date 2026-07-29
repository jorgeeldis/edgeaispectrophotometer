from arduino.app_utils import *
from arduino.app_bricks.web_ui import WebUI

ui = WebUI()

# Global variable to temporarily hold the latest data from the hardware
latest_hardware_data = []

# This receives the array from the Arduino C++ (MCU) side
def process_array(val1):
    global latest_hardware_data
    # Reassemble/save the incoming sensor data array 
    latest_hardware_data = val1 
    print(f"Hardware updated Array Data: {latest_hardware_data}")
    return val1

# Register the Bridge listener so the MCU side can pipe data up to Python
Bridge.provide("sendChannels", process_array)

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
    pass

App.run(user_loop=loop)
