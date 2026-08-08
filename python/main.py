from arduino.app_utils import *
from arduino.app_bricks.web_ui import WebUI
from arduino.app_bricks.dbstorage_sqlstore import SQLStore
import numpy as np
import math
import json
import datetime
import sqlite3

ui = WebUI()

# Stores the latest spectrum received from Arduino
latest_hardware_data = []
baseline = []
lastScan = []
latest_baseline_id = None

db = SQLStore("edgeaispectrophotometer.db")

columnsBaseline = {
    "id": "INTEGER PRIMARY KEY",
    "created_at": "TEXT",
    "raw_counts": "TEXT",       # JSON [12] — white, LED on, distilled water
    "dark_counts": "TEXT",      # JSON [12] — carried from dark calibration
    "dark_std": "TEXT",         # JSON [12] — noise floor, feeds Maintenance
    "n_burst": "INTEGER",
    "is_active": "INTEGER",
}

columnsMeasurement = {
    "id": "INTEGER PRIMARY KEY",
    "created_at": "TEXT",
    "name": "TEXT",
    "category": "TEXT",
    "baseline_id": "INTEGER",
    "raw_counts": "TEXT",       # JSON [12] — source of truth
    "saturated": "INTEGER",
    "is_reference": "INTEGER",
    "known_value": "REAL",      # NULL when unlabeled
}

columnsProfile = {
    "id": "INTEGER PRIMARY KEY",
    "created_at": "TEXT",
    "category": "TEXT",
    "channel_means": "TEXT",    # JSON [12]
    "channel_stds": "TEXT",     # JSON [12]
    "n_samples": "INTEGER",
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
    "is_active": "INTEGER",
}

db.create_table("baseline", columnsBaseline)
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

    #print("Received from Arduino:")
    #print(latest_hardware_data)


# Register callback once
Bridge.provide(
    "record_sensor_samples",
    record_sensor_samples
)


# Frontend requests latest spectrum
@ui.sio.on('run_arduino_function')
async def handle_frontend_request(sid, data=None):

    global baseline, latest_baseline_id

    baseline = latest_hardware_data

    print("Frontend requested hardware baseline scan...")

    if baseline:
        latest_baseline_id = db.store("baseline", {
            "created_at": datetime.datetime.utcnow().isoformat(),
            "raw_counts": json.dumps(baseline),
            "dark_counts": json.dumps([]),
            "dark_std": json.dumps([]),
            "n_burst": 1,
            "is_active": 1,
        })
        print(f"Saved baseline row id: {latest_baseline_id}")
    else:
        print("No baseline data available to save.")

    print(
        f"Sending data to frontend: {baseline}"
    )

    await ui.sio.emit('sendBaseline', baseline)


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

async def save_measurement(sid, data):

    print("save_measurement received data:", data)

    conn = sqlite3.connect('edgeaispectrophotometer.db')
    cursor = conn.cursor()

    # 1. Added LIMIT 1 to prevent multiple rows if timestamps tie
    cursor.execute("""
        SELECT id FROM baseline 
        WHERE created_at = (SELECT MAX(created_at) FROM baseline) 
        LIMIT 1;
    """)

    # 2. Use fetchone() instead of fetchall()
    row = cursor.fetchone()

    if row:
        last_id_baseline = row[0]  # Extracts the clean number from the tuple
        print(last_id_baseline)     # Outputs: 5
    else:
        last_id_baseline = None     # Handles the case where the table is empty

    conn.close()


    try:
        measurement_id = db.store("measurement", {
            "created_at": data.get("created_at") or datetime.datetime.utcnow().isoformat(),
            "name": data.get("name"),
            "category": data.get("category"),
            "baseline_id": last_id_baseline,
            "raw_counts": json.dumps(data.get("raw_counts")),
            "saturated": int(data.get("saturated")),
            "is_reference": int(data.get("is_reference")),
            "known_value": data.get("known_value"),
        })

        print(f"Saved measurement row id: {measurement_id}")
        await ui.sio.emit('saveDataResponse', {"success": True, "filePath": "edgeaispectrophotometer.db"}, room=sid)
    except Exception as e:
        print("save_measurement failed:", e)
        await ui.sio.emit('saveDataResponse', {"success": False, "error": str(e)}, room=sid)


@ui.sio.on('save_data')
async def handle_save_data(sid, data):
    await save_measurement(sid, data)


@ui.sio.on('save_scan_data')
async def handle_save_scan_data(sid, data):
    await save_measurement(sid, data)


@ui.sio.on('get_saved_measurements')
async def handle_get_saved_measurements(sid, data=None):
    measurements = get_saved_measurements()
    await ui.sio.emit('savedMeasurements', measurements, room=sid)


def get_saved_measurements():
    conn = sqlite3.connect('edgeaispectrophotometer.db')
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute(
        'SELECT id, created_at, name, category, baseline_id, raw_counts, saturated, is_reference, known_value FROM measurement ORDER BY created_at DESC'
    )
    rows = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return rows


def loop():
    pass


App.run(user_loop=loop)