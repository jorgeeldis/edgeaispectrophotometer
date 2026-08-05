from arduino.app_utils import *
from arduino.app_bricks.web_ui import WebUI
from arduino.app_bricks.dbstorage_sqlstore import SQLStore
import numpy as np
import math

ui = WebUI()

# Stores the latest spectrum received from Arduino
latest_hardware_data = []
baseline = []
lastScan = []

db = SQLStore("edgeaispectrophotometer.db")

columnsCalibration = {
    "id": "INTEGER PRIMARY KEY",
    "created_at": "TEXT",
    "dark_counts": "TEXT",      # JSON [12]
    "dark_std": "TEXT",         # JSON [12] — noise floor
    "white_counts": "TEXT",     # JSON [12]
    "gain": "INTEGER",
    "atime": "INTEGER",
    "astep": "INTEGER",
    "n_burst": "INTEGER",
    "is_active": "INTEGER",
}

columnsMeasurement = {
    "id": "INTEGER PRIMARY KEY",
    "created_at": "TEXT",
    "name": "TEXT",
    "category": "TEXT",
    "calibration_id": "INTEGER",
    "raw_counts": "TEXT",       # JSON [12] — source of truth
    "saturated": "INTEGER",
    "is_reference": "INTEGER",
    "known_value": "REAL",      # NULL when unlabeled
    "cal_tag": "TEXT",          # "4,19,99"
    "notes": "TEXT",
}

columnsProfile = {
    "id": "INTEGER PRIMARY KEY",
    "created_at": "TEXT",
    "category": "TEXT",
    "channel_means": "TEXT",    # JSON [12]
    "channel_stds": "TEXT",     # JSON [12]
    "n_samples": "INTEGER",
    "cal_tag": "TEXT",
    "is_active": "INTEGER",
}

columnsModel = {
    "id": "INTEGER PRIMARY KEY",
    "created_at": "TEXT",
    "category": "TEXT",
    "path": "TEXT",
    "n_samples": "INTEGER",
    "n_components": "INTEGER",
    "r2": "REAL", "rmse": "REAL", "mae": "REAL",
    "cal_tag": "TEXT",
    "is_active": "INTEGER",
}

db.create_table("calibration", columnsCalibration)
db.create_table("measurement", columnsMeasurement)
db.create_table("reference_profile", columnsProfile)
db.create_table("model", columnsModel)

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

    global baseline 

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

    print("This is baseline: ", baseline)
    print("This is latest: ", latest_hardware_data)

    lastScan = [math.log10(baseline[i] / latest_hardware_data[i]) for i in range(len(baseline))]

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