from arduino.app_utils import *
from arduino.app_bricks.web_ui import WebUI

ui = WebUI()

# Stores the latest spectrum received from Arduino
latest_hardware_data = []


# This receives data from the Arduino C++ sketch
def receive_channels(data):
    global latest_hardware_data

    latest_hardware_data = list(data)

    print("Received:", latest_hardware_data)


# Register the Arduino → Python callback ONCE
Bridge.provide("sendChannels", receive_channels)


# Frontend requests the latest data
@ui.sio.on('run_arduino_function')
async def handle_frontend_request(sid, data=None):

    print("Frontend requested hardware baseline scan...")

    # Send the latest Arduino data to the frontend
    print(f"Sending data to frontend: {latest_hardware_data}")

    await ui.sio.emit(
        'sendChannels',
        latest_hardware_data
    )


def loop():
    pass


App.run(user_loop=loop)