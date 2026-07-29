from arduino.app_utils import *
from arduino.app_bricks.web_ui import WebUI

ui = WebUI()

latest_hardware_data = []

def process_array(payload):
    global latest_hardware_data
    try:
        latest_hardware_data = [int(v) for v in str(payload).split(",")]
        print(f"Channels: {latest_hardware_data}")
    except ValueError:
        print(f"Bad payload: {payload!r}")
    return "ok"

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
