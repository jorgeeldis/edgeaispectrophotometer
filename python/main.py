from arduino.app_utils import *
from arduino.app_bricks.web_ui import WebUI

ui = WebUI()

# Stores the latest spectrum received from Arduino
latest_hardware_data = []


# Arduino MCU → Python MPU
def record_sensor_samples(
    F1: float,
    F2: float,
    FZ: float,
    F3: float,
    F4: float,
    F5: float,
    FY: float,
    FXL: float,
    F6: float,
    F7: float,
    F8: float,
    NIR: float
):
    global latest_hardware_data

    latest_hardware_data = [
        F1, F2, FZ, F3, F4, F5,
        FY, FXL, F6, F7, F8, NIR
    ]

    print("Received from Arduino:")
    print(latest_hardware_data)


# Register callback once
Bridge.provide(
    "record_sensor_samples",
    record_sensor_samples
)


# Frontend requests latest spectrum
@ui.sio.on('run_arduino_function')
async def handle_frontend_request(sid, data=None):

    print("Frontend requested hardware baseline scan...")

    print(
        f"Sending data to frontend: "
        f"{latest_hardware_data}"
    )

    await ui.sio.emit(
        'sendChannels',
        latest_hardware_data
    )


def loop():
    pass


App.run(user_loop=loop)