from arduino.app_utils import *
from arduino.app_bricks.web_ui import WebUI
from arduino.app_bricks.dbstorage_sqlstore import SQLStore
from datetime import datetime
import numpy as np
import json, math

ui = WebUI()
db = SQLStore("edgeaispectrophotometer.db")

N_CH = 12
WAVELENGTHS = [405, 425, 450, 475, 515, 555, 600, 640, 690, 745, 855, 940]
SATURATION = 65000

# ... table definitions unchanged, minus cal_tag/notes ...

state = {
    "latest": None,        # last spectrum pushed by the sketch
    "baseline_id": None,   # active baseline row
    "white": None,
    "dark": None,
    "dark_std": None,
}


# ------------------------------------------------ Arduino -> Python

def record_sensor_samples(begin, F1, F2, FZ, F3, F4, F5,
                          FY, FXL, F6, F7, F8, NIR, end):
    """Sketch pushes a spectrum. begin/end are framing sentinels."""
    state["latest"] = [F1, F2, FZ, F3, F4, F5, FY, FXL, F6, F7, F8, NIR]
    return "ok"

Bridge.provide("record_sensor_samples", record_sensor_samples)


# ------------------------------------------------ helpers

def acquire():
    """Trigger a fresh scan and wait for the push. None on timeout."""
    state["latest"] = None
    Bridge.call("scanNow")
    for _ in range(50):                      # ~5 s
        if state["latest"] is not None:
            return state["latest"]
        time.sleep(0.1)
    return None


def absorbance(raw):
    """A = -log10((sample - dark) / (white - dark)), clamped."""
    if state["white"] is None or state["dark"] is None:
        return None
    out = []
    for i in range(N_CH):
        num = raw[i] - state["dark"][i]
        den = state["white"][i] - state["dark"][i]
        if den <= 0 or num <= 0:
            out.append(0.0)                  # dead channel or over-range
        else:
            out.append(round(-math.log10(min(num / den, 1.0)), 4))
    return out


def active_baseline():
    rows = db.read("baseline")
    live = [r for r in rows if r.get("is_active")]
    return live[-1] if live else None


# ------------------------------------------------ frontend

@ui.sio.on("capture_baseline")
async def handle_baseline(sid, data=None):
    raw = acquire()
    if raw is None:
        await ui.sio.emit("error", {"msg": "Baseline timed out"}, to=sid)
        return

    # dark carried from the stored dark calibration; zeros until captured
    dark = state["dark"] or [0.0] * N_CH
    dark_std = state["dark_std"] or [0.0] * N_CH

    for r in db.read("baseline"):            # deactivate previous
        if r.get("is_active"):
            db.update("baseline", {"is_active": 0}, {"id": r["id"]})

    db.store("baseline", {
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "raw_counts": json.dumps(raw),
        "dark_counts": json.dumps(dark),
        "dark_std": json.dumps(dark_std),
        "n_burst": 1,
        "is_active": 1,
    })

    row = active_baseline()
    state["baseline_id"] = row["id"] if row else None
    state["white"] = raw
    state["dark"] = dark

    await ui.sio.emit("baseline_result", {
        "raw": raw,
        "dark_std": dark_std,
        "saturated": any(v >= SATURATION for v in raw),
    })


@ui.sio.on("single_scan")
async def handle_scan(sid, data=None):
    raw = acquire()
    if raw is None:
        await ui.sio.emit("error", {"msg": "Scan timed out"}, to=sid)
        return

    state["lastScan"] = raw
    await ui.sio.emit("scan_result", {
        "raw": raw,
        "absorbance": absorbance(raw),
        "saturated": any(v >= SATURATION for v in raw),
    })


@ui.sio.on("save_scan_data")
async def handle_save(sid, data):
    if state["baseline_id"] is None:
        await ui.sio.emit("error", {"msg": "No baseline — press Baseline first."}, to=sid)
        return
    try:
        db.store("measurement", {
            "created_at": datetime.now().isoformat(timespec="seconds"),
            "name": data["name"],
            "category": data["category"],
            "baseline_id": state["baseline_id"],
            "raw_counts": json.dumps(data["raw_counts"]),
            "saturated": int(data["saturated"]),
            "is_reference": int(data["is_reference"]),
            "known_value": data.get("known_value"),
        })
        await ui.sio.emit("save_ok", {"name": data["name"]}, to=sid)
    except Exception as e:
        await ui.sio.emit("error", {"msg": f"Save failed: {e}"}, to=sid)


def loop():
    pass

App.run(user_loop=loop)