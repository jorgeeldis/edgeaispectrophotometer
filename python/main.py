from arduino.app_utils import *
from arduino.app_bricks.web_ui import WebUI
import numpy as np

ui = WebUI()

# Stores the latest spectrum received from Arduino
latest_hardware_data = []
baseline = []
lastScan = []


# Arduino MCU → Python MPU
def record_sensor_samples(
    begin: float,
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
    NIR: float,
    end: float
):
    global latest_hardware_data

    latest_hardware_data = [
        begin, F1, F2, FZ, F3, F4, F5,
        FY, FXL, F6, F7, F8, NIR, end
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

    baseline = latest_hardware_data

    print("Frontend requested hardware baseline scan...")

    print(
        f"Sending data to frontend: "
        f"{baseline}"
    )

    await ui.sio.emit(
        'sendBaseline',
        baseline
    )

@ui.sio.on('get_single_scan')
async def frontend_request_single_scan(sid, data=None):

    lastScan = np.array(baseline)/np.array(latest_hardware_data)

    print("Frontend requested hardware single scan...")

    print(
        f"Sending data to frontend: "
        f"{lastScan}"
    )

    await ui.sio.emit(
        'sendSingleScan',
        lastScan
    )

def loop():
    pass


App.run(user_loop=loop)