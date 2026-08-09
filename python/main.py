from arduino.app_utils import *
from arduino.app_bricks.web_ui import WebUI
from arduino.app_bricks.dbstorage_sqlstore import SQLStore
import numpy as np
import math
import json
import datetime

ui = WebUI()
db = SQLStore("edgeaispectrophotometer.db")

N_CH = 12
WAVELENGTHS = [405, 425, 450, 475, 515, 550, 555, 600, 640, 690, 745, 855]
SATURATION = 65000

# Dark reference — captured once and reused across sessions.
# Replace with a real dark calibration burst; zeros until then.
DARK_COUNTS = [0.0] * N_CH
DARK_STD    = [0.0] * N_CH

state = {
    "latest": None,        # last spectrum pushed by the sketch (raw counts)
    "white": None,         # active baseline white counts
    "dark": DARK_COUNTS,
    "dark_std": DARK_STD,
    "baseline_id": None,
    "last_scan": None,     # {"raw": [...], "absorbance": [...], "saturated": bool}
}


# ------------------------------------------------ schema

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
    "raw_counts": "TEXT",       # JSON [12] — counts, audit trail
    "absorbance": "TEXT",       # JSON [12] — derived at capture, what readers use
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


# ------------------------------------------------ helpers

def now():
    return datetime.datetime.now().isoformat(timespec="seconds")


def compute_absorbance(raw, white, dark):
    """A = -log10((sample - dark) / (white - dark)), per channel."""
    if not white or not raw:
        return None
    out = []
    for i in range(N_CH):
        num = raw[i] - dark[i]
        den = white[i] - dark[i]
        if den <= 0 or num <= 0:
            out.append(0.0)                       # dead channel
        else:
            out.append(round(-math.log10(min(num / den, 1.0)), 4))
    return out


def active_baseline():
    rows = [dict(r) for r in db.read("baseline")]
    live = [r for r in rows if r.get("is_active")]
    return (live or rows)[-1] if rows else None


def load_vec(s):
    """Tolerate legacy 14-value rows with sentinels."""
    v = json.loads(s) if isinstance(s, str) else (s or [])
    return v[1:13] if len(v) == 14 else v[:N_CH]


def restore_state():
    """Rehydrate the active baseline after a restart."""
    b = active_baseline()
    if not b:
        return
    state["baseline_id"] = b["id"]
    state["white"] = load_vec(b["raw_counts"])
    d = load_vec(b["dark_counts"])
    if len(d) == N_CH:
        state["dark"] = d
    ds = load_vec(b["dark_std"])
    if len(ds) == N_CH:
        state["dark_std"] = ds
    print(f">>> restored baseline {b['id']}", flush=True)


# ------------------------------------------------ Arduino -> Python

def record_sensor_samples(F1: float, F2: float, FZ: float, F3: float,
                          F4: float, F5: float, FY: float, FXL: float,
                          F6: float, F7: float, F8: float, NIR: float):
    state["latest"] = [F1, F2, FZ, F3, F4, F5, FY, FXL, F6, F7, F8, NIR]


Bridge.provide("record_sensor_samples", record_sensor_samples)


# ------------------------------------------------ baseline

@ui.sio.on('run_arduino_function')
async def handle_baseline(sid, data=None):
    raw = state["latest"]
    if not raw:
        await ui.sio.emit('error', {"msg": "No sensor data yet"}, room=sid)
        return

    # deactivate previous baselines
    for r in db.read("baseline"):
        r = dict(r)
        if r.get("is_active"):
            try:
                db.update("baseline", {"is_active": 0}, {"id": r["id"]})
            except Exception:
                pass                              # brick may lack update()

    db.store("baseline", {
        "created_at": now(),
        "raw_counts": json.dumps(raw),
        "dark_counts": json.dumps(state["dark"]),
        "dark_std": json.dumps(state["dark_std"]),
        "n_burst": 1,
        "is_active": 1,
    })

    b = active_baseline()
    state["baseline_id"] = b["id"] if b else None
    state["white"] = raw
    state["last_scan"] = None

    saturated = any(v >= SATURATION for v in raw)
    print(f">>> baseline {state['baseline_id']} stored, saturated={saturated}", flush=True)

    await ui.sio.emit('sendBaseline', {
        "raw": raw,
        "dark_std": state["dark_std"],
        "saturated": saturated,
    }, room=sid)


# ------------------------------------------------ single scan

@ui.sio.on('get_single_scan')
async def handle_single_scan(sid, data=None):
    raw = state["latest"]
    if not raw:
        await ui.sio.emit('error', {"msg": "No sensor data yet"}, room=sid)
        return
    if not state["white"]:
        await ui.sio.emit('error', {"msg": "No baseline — press Baseline first"}, room=sid)
        return

    absorb = compute_absorbance(raw, state["white"], state["dark"])
    saturated = any(v >= SATURATION for v in raw)

    state["last_scan"] = {"raw": raw, "absorbance": absorb, "saturated": saturated}

    await ui.sio.emit('sendSingleScan', {
        "raw": raw,
        "absorbance": absorb,
        "saturated": saturated,
    }, room=sid)


# ------------------------------------------------ save

async def save_measurement(sid, data):
    scan = state["last_scan"]
    if not scan:
        await ui.sio.emit('saveDataResponse',
                          {"success": False, "error": "No scan to save"}, room=sid)
        return
    if state["baseline_id"] is None:
        await ui.sio.emit('saveDataResponse',
                          {"success": False, "error": "No baseline"}, room=sid)
        return

    is_ref = int(data.get("is_reference") or 0)
    known  = 0.0 if is_ref else data.get("known_value")

    try:
        db.store("measurement", {
            "created_at": now(),
            "name": data.get("name"),
            "category": data.get("category"),
            "baseline_id": state["baseline_id"],
            "raw_counts": json.dumps(scan["raw"]),
            "absorbance": json.dumps(scan["absorbance"]),
            "saturated": int(scan["saturated"]),
            "is_reference": is_ref,
            "known_value": known,
        })
        print(f">>> saved {data.get('name')}", flush=True)
        await ui.sio.emit('saveDataResponse',
                          {"success": True, "name": data.get("name")}, room=sid)
    except Exception as e:
        print(">>> save failed:", e, flush=True)
        await ui.sio.emit('saveDataResponse',
                          {"success": False, "error": str(e)}, room=sid)


@ui.sio.on('save_data')
async def handle_save_data(sid, data):
    await save_measurement(sid, data)


@ui.sio.on('save_scan_data')
async def handle_save_scan_data(sid, data):
    await save_measurement(sid, data)


# ------------------------------------------------ measures

@ui.sio.on('get_saved_measurements')
async def handle_get_saved_measurements(sid, data=None):
    rows = []
    for r in db.read("measurement"):
        r = dict(r)
        rows.append({
            "id": r["id"],
            "created_at": r["created_at"],
            "name": r["name"],
            "category": r["category"],
            "absorbance": load_vec(r.get("absorbance") or r["raw_counts"]),
            "saturated": r["saturated"],
            "is_reference": r["is_reference"],
            "known_value": r["known_value"],
        })
    rows.sort(key=lambda x: x["created_at"], reverse=True)
    await ui.sio.emit('savedMeasurements', rows, room=sid)


# ------------------------------------------------ analysis

@ui.sio.on('get_analysis')
async def handle_analysis(sid, data=None):
    category = (data or {}).get("category")

    measurements = [dict(r) for r in db.read("measurement")]
    rows = ([m for m in measurements if m["category"] == category]
            if category else measurements)

    def absorbance_of(m):
        v = load_vec(m.get("absorbance") or m["raw_counts"])
        return v if len(v) == N_CH else None

    # reference profile per category — milk refs can't score coffee
    profiles = {}
    by_cat = {}
    for m in measurements:
        if m["is_reference"]:
            a = absorbance_of(m)
            if a:
                by_cat.setdefault(m["category"], []).append(a)

    for cat, refs in by_cat.items():
        print(f">>> {cat}: {len(refs)} refs", flush=True)
        if len(refs) >= 2:
            arr = np.array(refs)
            profiles[cat] = (arr.mean(axis=0),
                             np.maximum(arr.std(axis=0, ddof=1), 1e-6))

    out = []
    for m in rows:
        a = absorbance_of(m)
        dev = None
        prof = profiles.get(m["category"])
        if a and prof:
            means, stds = prof
            z = (np.array(a) - means) / stds
            dev = round(float(np.sqrt(np.mean(z ** 2))), 2)   # RMS z-score

        out.append({
            "id": m["id"],
            "name": m["name"],
            "category": m["category"],
            "dev": dev,
            "pred": None,          # awaits a trained model
            "conf": None,
            "status": (None if dev is None else
                       "PASS" if dev < 2 else "ATTENTION" if dev < 3 else "REJECT"),
            "is_reference": m["is_reference"],
            "known_value": m["known_value"],
        })

    print(f">>> emitting {len(out)} rows", flush=True)
    await ui.sio.emit('analysisData', out, room=sid)


restore_state()


def loop():
    pass


App.run(user_loop=loop)