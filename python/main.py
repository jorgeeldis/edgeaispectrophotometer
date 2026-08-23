from arduino.app_utils import *
from arduino.app_bricks.web_ui import WebUI
from arduino.app_bricks.dbstorage_sqlstore import SQLStore
from arduino.app_bricks.llm import LargeLanguageModel, tool
from arduino.app_bricks.cloud_llm import SQLMessagePersistence
import numpy as np
import math
import json
import datetime
import asyncio
import os
import traceback
from html import escape as _esc
import pandas

ui = WebUI()

# assets/ sits next to python/ in the project layout; WebUI serves assets/
# from disk, so anything written under REPORTS_DIR is immediately reachable
# from the browser at the relative URL "reports/<filename>" with no extra
# server route needed.
REPORTS_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "assets", "reports")

# Stores the latest spectrum received from Arduino
latest_hardware_data = []
baseline = []
lastScan = []
latest_baseline_id = None

# scan_counter and last_baseline_at are the only fields here derived from
# real, live state (see compute_calibration_health). temperature_c, sensor_health,
# led_hours, and baseline_drift_percent are prototype placeholders — nothing
# currently reads real telemetry for them; temperature_c just nudges up 0.1°C
# per saved measurement as a stand-in until real sensor readout is wired up.
maintenance_state = {
    "scan_counter": 0,
    "last_baseline_at": None,
    "temperature_c": 31.4,
    "sensor_health": "healthy",
    "led_hours": 142.0,
    "firmware_version": "v0.4.1",
    "dark_reference_age_hours": 18.0,
    "baseline_drift_percent": 1.4,
    "calibration_status": "attention",
    "service_due_date": None,
}

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
    "coeffs": "TEXT",
    "intercept": "REAL",
    "n_samples": "INTEGER",
    "n_components": "INTEGER",
    "r2": "REAL", "rmse": "REAL", "mae": "REAL",
    "is_active": "INTEGER",
}

columnsReport = {
    "id": "INTEGER PRIMARY KEY",
    "created_at": "TEXT",
    "category": "TEXT",
    "type": "TEXT",
    "profile_id": "INTEGER",
    "model_id": "INTEGER",
    "path": "TEXT",
    "description": "TEXT",
    "is_active": "INTEGER",
}

db.create_table("baseline", columnsBaseline)
db.create_table("measurement", columnsMeasurement)
db.create_table("reference_profile", columnsProfile)
db.create_table("model", columnsModel)
db.create_table("report", columnsReport)


def decode_spectrum(value):
    if value is None:
        return np.zeros(12, dtype=float)
    try:
        arr = json.loads(value)
    except Exception:
        try:
            arr = value if isinstance(value, list) else [value]
        except Exception:
            arr = []
    if not isinstance(arr, list):
        return np.zeros(12, dtype=float)
    arr = np.asarray(arr, dtype=float)
    if arr.size == 0:
        return np.zeros(12, dtype=float)
    if arr.size > 12:
        arr = arr[:12]
    if arr.size < 12:
        pad = np.zeros(12 - arr.size, dtype=float)
        arr = np.concatenate([arr, pad])
    return arr.astype(float)


def normalize_spectrum(raw):
    arr = np.asarray(raw, dtype=float)
    if arr.size == 0:
        return None
    if arr.size > 12:
        arr = arr[:12]
    if arr.size < 12:
        return None
    return arr.astype(float)


def get_active_profile(category):
    profiles = [dict(r) for r in db.read("reference_profile") if str(r.get("category")) == str(category)]
    for profile in reversed(profiles):
        if int(profile.get("is_active", 0)):
            return profile
    return None


def get_active_model(category):
    models = [dict(r) for r in db.read("model") if str(r.get("category")) == str(category)]
    for model in reversed(models):
        if int(model.get("is_active", 0)):
            return model
    return None


def compute_calibration_health():
    # Three independent signals escalate the status together rather than a
    # single flag, so an operator can see *why* recalibration is being asked
    # for (too many scans since baseline vs. baseline just getting old vs.
    # measured drift) instead of a single opaque "needs attention".
    now = datetime.datetime.utcnow()
    age_hours = 0.0
    if maintenance_state["last_baseline_at"] is not None:
        age_hours = max(0.0, (now - maintenance_state["last_baseline_at"]).total_seconds() / 3600.0)
    maintenance_state["dark_reference_age_hours"] = round(age_hours, 1)

    drift = max(0.0, float(maintenance_state["baseline_drift_percent"]))
    counter = int(maintenance_state["scan_counter"])

    if counter >= 10 or age_hours >= 8 or drift >= 10:
        maintenance_state["calibration_status"] = "warning"
    elif counter >= 5 or age_hours >= 5 or drift >= 5:
        maintenance_state["calibration_status"] = "attention"
    else:
        maintenance_state["calibration_status"] = "healthy"

    return {
        "status": maintenance_state["calibration_status"],
        "scan_counter": counter,
        "dark_reference_age_hours": maintenance_state["dark_reference_age_hours"],
        "baseline_drift_percent": drift,
        "temperature_c": maintenance_state["temperature_c"],
        "sensor_health": maintenance_state["sensor_health"],
        "led_hours": maintenance_state["led_hours"],
        "firmware_version": maintenance_state["firmware_version"],
    }


def predict_with_model(model, spectrum):
    if not model:
        return None, None
    try:
        coeffs = np.asarray(json.loads(model.get("coeffs", "[]")), dtype=float)
    except Exception:
        coeffs = np.asarray([], dtype=float)
    intercept = float(model.get("intercept", 0.0) or 0.0)
    if coeffs.size == 0:
        return None, None
    spec = np.asarray(spectrum, dtype=float)
    if spec.size < coeffs.size:
        spec = np.pad(spec, (0, coeffs.size - spec.size), constant_values=0.0)
    pred = float(np.dot(coeffs[:spec.size], spec[:coeffs.size]) + intercept)
    # Confidence is a simple heuristic derived from training RMSE, not a
    # statistical prediction interval — a tighter-fitting model (lower RMSE)
    # reports higher confidence, floored so a very noisy fit never claims 0%
    # and capped at 100%.
    conf = max(0.0, min(1.0, 1.0 / (1.0 + max(float(model.get("rmse", 0.0) or 0.0), 0.05))))
    return pred, round(conf, 4)


def compute_dev_status(known_value, means, stds, arr, model, pred):
    """
    Deviation-from-reference-profile is the right check for a true unknown:
    it answers "does this look like a good sample of this category". It is
    the WRONG check for a labeled calibration/training sample — a 50%
    dilution is *supposed* to sit far from the 0% reference, so scoring it
    against the profile flags legitimate training data as REJECT.

    So: labeled samples with an active model are scored on how far the
    model's own prediction misses their declared known_value, scaled by the
    model's own RMSE (its own notion of "one unit of expected error").
    Everything else falls back to the reference-profile z-score. Either way
    the same PASS/ATTENTION/REJECT thresholds apply to whichever "dev" ends
    up meaning in context.
    """
    if known_value is not None and pred is not None and model:
        rmse = max(float(model.get("rmse", 0.0) or 0.0), 1e-6)
        dev = round(abs(float(pred) - float(known_value)) / rmse, 2)
    elif means is not None and stds is not None:
        z = (arr - means) / stds
        dev = round(float(np.sqrt(np.mean(z ** 2))), 2)
    else:
        dev = None

    status = None if dev is None else "PASS" if dev < 2 else "ATTENTION" if dev < 3 else "REJECT"
    return dev, status


# Tools the on-device LLM can call to look up real instrument data
# instead of guessing at measurements, calibration, or model quality.

@tool
def get_recent_measurements(category: str = "") -> str:
    """
    Return a short summary of the most recently saved measurements.
    If category is one of Water, Coffee, Milk or Other, only that
    category's most recent rows are included.
    """
    rows = [dict(r) for r in db.read("measurement")]
    if category:
        rows = [r for r in rows if str(r.get("category")) == str(category)]
    rows = rows[-5:]
    if not rows:
        return "No measurements have been saved yet."
    lines = [
        f"{r.get('name')} ({r.get('category')}): known_value={r.get('known_value')}, "
        f"is_reference={bool(r.get('is_reference'))}"
        for r in rows
    ]
    return "Most recent measurements:\n" + "\n".join(lines)


@tool
def get_calibration_status() -> str:
    """
    Return the instrument's current calibration and maintenance status:
    calibration health, scans since last baseline, dark reference age,
    baseline drift percent, sensor health, LED hours and firmware version.
    """
    health = compute_calibration_health()
    return (
        f"Calibration status: {health['status']}. "
        f"Scans since last baseline: {health['scan_counter']}. "
        f"Dark reference age: {health['dark_reference_age_hours']} h. "
        f"Baseline drift: {health['baseline_drift_percent']}%. "
        f"Sensor health: {health['sensor_health']}. "
        f"LED hours: {health['led_hours']}. "
        f"Firmware: {health['firmware_version']}."
    )


@tool
def get_active_model_metrics(category: str) -> str:
    """
    Return the training metrics (R^2, RMSE, MAE, sample count) of the
    active prediction model for a given category (Water, Coffee, Milk
    or Other), if one has been trained.
    """
    model = get_active_model(category)
    if not model:
        return f"No trained model is active for category '{category}'."
    return (
        f"Active model for {category}: R^2={model.get('r2')}, "
        f"RMSE={model.get('rmse')}, MAE={model.get('mae')}, "
        f"trained on {model.get('n_samples')} samples."
    )


llm = LargeLanguageModel(
    system_prompt=(
        "You are the on-device analysis assistant for an edge AI spectrophotometer. "
        "Answer questions about the instrument, its measurements, calibration status, "
        "and trained prediction models. Use the provided tools to look up real data "
        "instead of guessing. Keep answers concise."
    ),
    tools=[get_recent_measurements, get_calibration_status, get_active_model_metrics],
).with_memory(
    max_messages=10,
    persistence=SQLMessagePersistence(sql_store=db, thread_id="analysis-assistant"),
)


# Arduino MCU → Python MPU
# Registered below with Bridge.provide("record_sensor_samples", ...) — the
# firmware's Bridge.notify() call in sketch.ino's loop() lands here roughly
# every 2 seconds, continuously, whether or not anyone is looking at the UI.
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
    NIR: float,

):
    global latest_hardware_data

    latest_hardware_data = [
F1, F2, FZ, F3, F4, F5,
        FY, FXL, F6, F7, F8, NIR
    ]


# Register callback once
Bridge.provide(
    "record_sensor_samples",
    record_sensor_samples
)
Bridge.provide(
    "rpcGetTemp",
    lambda: maintenance_state["temperature_c"]
)
Bridge.provide(
    "rpcSensorPing",
    lambda: {"healthy": True, "status_register": 0, "sensor_health": maintenance_state["sensor_health"]}
)


# Frontend requests latest spectrum
@ui.sio.on('run_arduino_function')
async def handle_frontend_request(sid, data=None):

    global baseline, latest_baseline_id

    baseline = latest_hardware_data

    print("Frontend requested hardware baseline scan...")

    if baseline:
        maintenance_state["scan_counter"] = 0
        maintenance_state["last_baseline_at"] = datetime.datetime.utcnow()
        latest_baseline_id = db.store("baseline", {
            "created_at": maintenance_state["last_baseline_at"].isoformat(),
            "raw_counts": json.dumps(baseline),
            "dark_counts": json.dumps([]),
            "dark_std": json.dumps([]),
            "n_burst": 1,
            "is_active": 1,
        })
        print(f"Saved baseline row id: {latest_baseline_id}")
    else:
        print("No baseline data available to save.")

    print(f"Sending data to frontend: {baseline}")

    await ui.sio.emit('sendBaseline', baseline)


@ui.sio.on('get_single_scan')
async def frontend_request_single_scan(sid, data=None):

    print("This is baseline: ", baseline)
    print("This is latest: ", latest_hardware_data)

    if not baseline or not latest_hardware_data:
        print("Cannot compute single scan: baseline not captured yet.")
        await ui.sio.emit('scanError', {"message": "Capture a baseline before running a scan."}, room=sid)
        return

    # log10(baseline / sample) is the standard Beer-Lambert absorbance
    # transform; zip() also protects against baseline/latest_hardware_data
    # having drifted to different lengths, and the b/s > 0 guard avoids a
    # ZeroDivisionError or a log10 domain error on a dead/saturated channel.
    lastScan = [
        math.log10(b / s) if b > 0 and s > 0 else 0.0
        for b, s in zip(baseline, latest_hardware_data)
    ]

    print("Frontend requested hardware single scan...")

    print(f"Sending data to frontend: {lastScan}")

    await ui.sio.emit('sendSingleScan', lastScan)


async def save_measurement(sid, data):

    print("save_measurement received data:", data)

    baseline_rows = db.read("baseline")
    baseline_row = baseline_rows[-1] if baseline_rows else None
    baseline_id = baseline_row.get("id") if baseline_row else None
    print("the latest_baseline_id is ", baseline_id)

    try:
        payload = {
            "created_at": data.get("created_at") or datetime.datetime.utcnow().isoformat(),
            "name": data.get("name"),
            "category": data.get("category"),
            "raw_counts": json.dumps(data.get("raw_counts")),
            "saturated": int(data.get("saturated")),
            "is_reference": int(data.get("is_reference")),
        }
        # SQLStore rejects None outright, so nullable FK/optional columns are
        # only included when they actually have a value.
        if baseline_id is not None:
            payload["baseline_id"] = baseline_id
        known_value = data.get("known_value")
        if known_value is not None:
            payload["known_value"] = known_value

        measurement_id = db.store("measurement", payload)

        maintenance_state["scan_counter"] = int(maintenance_state.get("scan_counter", 0)) + 1
        maintenance_state["temperature_c"] = round(float(maintenance_state["temperature_c"]) + 0.1, 1)
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
    all_measurements = db.read("measurement")
    rows = [dict(row) for row in all_measurements]
    print("This are the rows", rows)
    await ui.sio.emit('savedMeasurements', rows, room=sid)


@ui.sio.on('build_reference')
async def handle_build_reference(sid, data=None):
    category = (data or {}).get("category") or "Other"
    rows = [dict(r) for r in db.read("measurement") if str(r.get("category")) == str(category) and int(r.get("is_reference", 0)) == 1]
    if len(rows) < 5:
        await ui.sio.emit('buildReferenceResponse', {"success": False, "reason": "Need at least 5 reference replicates before building a profile."}, room=sid)
        return

    spectra = []
    for row in rows:
        arr = normalize_spectrum(json.loads(row.get("raw_counts", "[]")))
        if arr is not None:
            spectra.append(arr)

    if len(spectra) < 5:
        await ui.sio.emit('buildReferenceResponse', {"success": False, "reason": "Reference rows were found but the spectra were missing or malformed."}, room=sid)
        return

    arr = np.vstack(spectra)
    means = arr.mean(axis=0)
    stds = np.maximum(arr.std(axis=0, ddof=1), 1e-6)

    existing = [dict(r) for r in db.read("reference_profile") if str(r.get("category")) == str(category)]
    for row in existing:
        # Drop "id" from the payload — it's already the row's own primary key,
        # so re-asserting it here (on top of passing it as the update target
        # below) risks store() treating this as an insert with a duplicate id.
        row_id = row.pop("id", None)
        db.store("reference_profile", {**row, "is_active": 0}, row_id)

    profile_id = db.store("reference_profile", {
        "created_at": datetime.datetime.utcnow().isoformat(),
        "category": category,
        "channel_means": json.dumps(means.tolist()),
        "channel_stds": json.dumps(stds.tolist()),
        "n_samples": len(spectra),
        "is_active": 1,
    })

    await ui.sio.emit('buildReferenceResponse', {"success": True, "category": category, "profile_id": profile_id, "n_samples": len(spectra)}, room=sid)


@ui.sio.on('sanity_plot')
async def handle_sanity_plot(sid, data=None):
    # Fits known concentration against summed signal and gates on R² before
    # Train Model is trusted — this exists to catch an optical or electronic
    # fault (bad seal, misaligned cuvette, dying LED) before it gets blamed
    # on the regression model instead of the instrument.
    category = (data or {}).get("category") or "Other"
    rows = [dict(r) for r in db.read("measurement") if str(r.get("category")) == str(category) and r.get("known_value") is not None]
    if len(rows) < 15:
        await ui.sio.emit('sanityPlotResponse', {"success": False, "reason": "Need at least 15 labeled rows for the sanity plot."}, room=sid)
        return

    by_level = {}
    for row in rows:
        val = float(row.get("known_value", 0.0))
        by_level.setdefault(val, []).append(normalize_spectrum(json.loads(row.get("raw_counts", "[]"))))
    if len(by_level) < 4:
        await ui.sio.emit('sanityPlotResponse', {"success": False, "reason": "Need at least 4 concentration levels for the sanity plot."}, room=sid)
        return

    x = []
    y = []
    for level, spectra in sorted(by_level.items()):
        clean = [s for s in spectra if s is not None]
        if not clean:
            continue
        x.append(float(level))
        y.append(float(np.mean(np.vstack(clean), axis=0).sum()))

    if len(x) < 4:
        await ui.sio.emit('sanityPlotResponse', {"success": False, "reason": "Not enough valid levels after filtering malformed spectra."}, room=sid)
        return

    x = np.asarray(x, dtype=float)
    y = np.asarray(y, dtype=float)
    slope, intercept = np.polyfit(x, y, 1)
    y_pred = slope * x + intercept
    ss_res = np.sum((y - y_pred) ** 2)
    ss_tot = np.sum((y - np.mean(y)) ** 2)
    r2 = 1.0 if ss_tot == 0 else float(1 - ss_res / ss_tot)

    reason = None if r2 > 0.99 else "Sanity plot drifted below R² > 0.99; check the optical path before training."
    await ui.sio.emit('sanityPlotResponse', {
        "success": r2 > 0.99,
        "category": category,
        "r2": round(r2, 4),
        "reason": reason,
        "levels": x.tolist(),
        "signal": y.tolist(),
        "fit_slope": float(slope),
        "fit_intercept": float(intercept),
    }, room=sid)


@ui.sio.on('train_model')
async def handle_train_model(sid, data=None):
    category = (data or {}).get("category") or "Other"
    rows = [dict(r) for r in db.read("measurement") if str(r.get("category")) == str(category) and r.get("known_value") is not None and int(r.get("is_reference", 0)) == 0]
    if len(rows) < 15:
        await ui.sio.emit('trainModelResponse', {"success": False, "reason": "Need at least 15 labeled rows to train a model."}, room=sid)
        return

    levels = {float(r.get("known_value")) for r in rows}
    if len(levels) < 4:
        await ui.sio.emit('trainModelResponse', {"success": False, "reason": "Need at least 4 concentration levels before training."}, room=sid)
        return

    X = []
    y = []
    for row in rows:
        spec = normalize_spectrum(json.loads(row.get("raw_counts", "[]")))
        if spec is None:
            continue
        X.append(spec)
        y.append(float(row.get("known_value", 0.0)))
    if len(X) < 15:
        await ui.sio.emit('trainModelResponse', {"success": False, "reason": "Not enough valid spectra after filtering malformed rows."}, room=sid)
        return

    X = np.vstack(X)
    y = np.asarray(y, dtype=float)
    # Ordinary least squares over the twelve raw channels — chosen for a
    # linear-in-concentration signal (Beer-Lambert) and a small per-category
    # sample count where a heavier model would just overfit. Note this is an
    # in-sample fit: R²/RMSE/MAE below are computed against the same rows
    # the model was trained on, not held-out cross-validation.
    coef, _, _, _ = np.linalg.lstsq(X, y, rcond=None)
    pred = X @ coef
    residual = y - pred
    ss_res = np.sum(residual ** 2)
    ss_tot = np.sum((y - np.mean(y)) ** 2)
    r2 = 1.0 if ss_tot == 0 else float(1 - ss_res / ss_tot)
    rmse = float(np.sqrt(np.mean(residual ** 2)))
    mae = float(np.mean(np.abs(residual)))

    existing = [dict(r) for r in db.read("model") if str(r.get("category")) == str(category)]
    for row in existing:
        # Same reasoning as the reference_profile deactivation in
        # handle_build_reference: drop "id" from the payload so it's never
        # re-asserted alongside the update-target id below.
        row_id = row.pop("id", None)
        db.store("model", {**row, "is_active": 0}, row_id)

    model_id = db.store("model", {
        "created_at": datetime.datetime.utcnow().isoformat(),
        "category": category,
        "path": f"{category.lower()}_model.json",
        "coeffs": json.dumps(coef.tolist()),
        "intercept": 0.0,
        "n_samples": int(len(X)),
        "n_components": min(3, len(coef)),
        "r2": float(r2),
        "rmse": float(rmse),
        "mae": float(mae),
        "is_active": 1,
    })

    await ui.sio.emit('trainModelResponse', {"success": True, "category": category, "model_id": model_id, "r2": round(float(r2),4), "rmse": round(float(rmse),4), "mae": round(float(mae),4)}, room=sid)


@ui.sio.on('get_reports')
async def handle_get_reports(sid, data=None):
    rows = [dict(r) for r in db.read("report")]
    await ui.sio.emit('reportsData', rows, room=sid)


# Renders a spectrum as a plain inline SVG polyline instead of pulling in a
# plotting library — the on-device runtime can't be assumed to have a full
# charting stack, and this keeps the generated report a single dependency-free
# HTML file.
def _svg_spectrum(values, width=520, height=120, color="#b6551c"):
    if not values:
        return "<p><em>No spectrum recorded.</em></p>"
    vmin, vmax = min(values), max(values)
    rng = (vmax - vmin) or 1.0
    n = len(values)
    step = width / max(n - 1, 1)
    points = []
    for i, v in enumerate(values):
        x = i * step
        y = height - ((v - vmin) / rng) * (height - 10) - 5
        points.append(f"{x:.1f},{y:.1f}")
    polyline = " ".join(points)
    return (
        f'<svg viewBox="0 0 {width} {height}" width="100%" height="{height}" '
        f'xmlns="http://www.w3.org/2000/svg" style="background:#fdfaf0;border:1px solid #ccc">'
        f'<polyline points="{polyline}" fill="none" stroke="{color}" stroke-width="2" /></svg>'
    )


def render_report_html(category, timestamp, baseline_row, profile, model, health, measurements):
    baseline_html = "<p><em>No baseline captured.</em></p>"
    if baseline_row:
        counts = json.loads(baseline_row.get("raw_counts") or "[]")
        baseline_html = (
            f"<p>Captured: {_esc(str(baseline_row.get('created_at')))}</p>"
            f"{_svg_spectrum(counts)}"
        )

    profile_html = "<p><em>No active reference profile for this category.</em></p>"
    if profile:
        profile_html = (
            f"<p>Built: {_esc(str(profile.get('created_at')))} "
            f"from {profile.get('n_samples')} replicates</p>"
        )

    model_html = "<p><em>No trained model for this category.</em></p>"
    if model:
        model_html = (
            f"<p>Trained: {_esc(str(model.get('created_at')))} "
            f"on {model.get('n_samples')} samples</p>"
            f"<p>R&sup2; = {model.get('r2')}, RMSE = {model.get('rmse')}, MAE = {model.get('mae')}</p>"
        )

    rows_html = ""
    for m in measurements:
        dev = m.get("dev")
        status = (
            "PASS" if dev is not None and dev < 2 else
            "ATTENTION" if dev is not None and dev < 3 else
            "REJECT" if dev is not None else "—"
        )
        rows_html += f"""
        <tr>
          <td>{_esc(str(m.get('name')))}</td>
          <td>{_esc(str(m.get('created_at')))}</td>
          <td>{m.get('known_value') if m.get('known_value') is not None else '—'}</td>
          <td>{'YES' if m.get('is_reference') else 'no'}</td>
          <td>{dev if dev is not None else '—'}</td>
          <td>{m.get('pred') if m.get('pred') is not None else '—'}</td>
          <td>{m.get('conf') if m.get('conf') is not None else '—'}</td>
          <td>{status}</td>
          <td style="min-width:160px">{_svg_spectrum(m.get('spectrum'))}</td>
        </tr>"""

    return f"""<!doctype html>
<html><head><meta charset="utf-8">
<title>{_esc(category)} Compliance Report</title>
<style>
  body {{ font-family: ui-monospace, Menlo, Consolas, monospace; padding: 24px; color: #2b2b1f; background: #FBF7EA; }}
  h1, h2 {{ margin-bottom: 4px; }}
  table {{ border-collapse: collapse; width: 100%; margin-top: 8px; }}
  th, td {{ border: 1px solid #ccc; padding: 6px 8px; font-size: 12px; text-align: left; }}
  section {{ margin-bottom: 24px; }}
</style>
</head>
<body>
  <h1>Edge-AI Spectrophotometer — Compliance Report</h1>
  <p>Category: <strong>{_esc(category)}</strong> &nbsp;|&nbsp; Generated: {timestamp.isoformat(timespec='seconds')}Z</p>

  <section>
    <h2>Instrument Status</h2>
    <p>Calibration: {_esc(str(health.get('status')))} &nbsp;|&nbsp;
       Dark reference age: {health.get('dark_reference_age_hours')} h &nbsp;|&nbsp;
       Baseline drift: {health.get('baseline_drift_percent')}% &nbsp;|&nbsp;
       Sensor: {_esc(str(health.get('sensor_health')))} &nbsp;|&nbsp;
       Firmware: {_esc(str(health.get('firmware_version')))}</p>
  </section>

  <section>
    <h2>Baseline Used</h2>
    {baseline_html}
  </section>

  <section>
    <h2>Active Reference Profile</h2>
    {profile_html}
  </section>

  <section>
    <h2>Active Prediction Model</h2>
    {model_html}
  </section>

  <section>
    <h2>Measurements ({len(measurements)})</h2>
    <table>
      <thead>
        <tr>
          <th>Name</th><th>Date</th><th>Known Value</th><th>Reference?</th>
          <th>Dev &sigma;</th><th>Pred</th><th>Conf</th><th>Status</th><th>Spectrum</th>
        </tr>
      </thead>
      <tbody>{rows_html}</tbody>
    </table>
  </section>
</body></html>"""


@ui.sio.on('export_report')
async def handle_export_report(sid, data=None):
    category = (data or {}).get("category") or "Other"
    try:
        profile = get_active_profile(category)
        model = get_active_model(category)
        health = compute_calibration_health()

        baseline_rows = db.read("baseline")
        baseline_row = dict(baseline_rows[-1]) if baseline_rows else None

        means = stds = None
        if profile:
            means = np.asarray(json.loads(profile["channel_means"]), dtype=float)
            stds = np.asarray(json.loads(profile["channel_stds"]), dtype=float)

        rows = [dict(r) for r in db.read("measurement") if str(r.get("category")) == str(category)][-20:]
        measurements = []
        for m in rows:
            arr = normalize_spectrum(json.loads(m.get("raw_counts", "[]")))
            dev = pred = conf = None
            if arr is not None:
                if model:
                    pred, conf = predict_with_model(model, arr)
                # Same logic as the Analysis tab (compute_dev_status) — keeps
                # exported reports consistent with what's shown live.
                dev, _ = compute_dev_status(m.get("known_value"), means, stds, arr, model, pred)
            measurements.append({
                "name": m.get("name"),
                "created_at": m.get("created_at"),
                "known_value": m.get("known_value"),
                "is_reference": bool(m.get("is_reference")),
                "dev": dev,
                "pred": None if pred is None else round(float(pred), 3),
                "conf": conf,
                "spectrum": arr.tolist() if arr is not None else None,
            })

        timestamp = datetime.datetime.utcnow()
        filename = f"{category.lower()}_{timestamp.strftime('%Y%m%d%H%M%S')}.html"
        rel_path = f"reports/{filename}"

        report_html = render_report_html(category, timestamp, baseline_row, profile, model, health, measurements)

        os.makedirs(REPORTS_DIR, exist_ok=True)
        with open(os.path.join(REPORTS_DIR, filename), "w", encoding="utf-8") as f:
            f.write(report_html)

        report_payload = {
            "created_at": timestamp.isoformat(),
            "category": category,
            "type": "Compliance Report",
            "path": rel_path,
            "description": f"{category} report ({len(measurements)} measurements)",
            "is_active": 1,
        }
        # SQLStore rejects None outright, so these optional FKs are only
        # included when there's an active profile/model to point at.
        if profile:
            report_payload["profile_id"] = profile.get("id")
        if model:
            report_payload["model_id"] = model.get("id")

        report_id = db.store("report", report_payload)
        await ui.sio.emit('reportSaved', {"success": True, "report_id": report_id, "path": rel_path, "category": category}, room=sid)
        await handle_get_reports(sid)
    except Exception as e:
        print("export_report failed:")
        traceback.print_exc()
        await ui.sio.emit('reportSaved', {"success": False, "error": str(e)}, room=sid)


@ui.sio.on('chat_send')
async def handle_chat_send(sid, data=None):
    question = (data or {}).get("question", "").strip()
    if not question:
        await ui.sio.emit('chatResponse', {"content": "Please ask a question about the instrument, a sample, or a calibration step."}, room=sid)
        return

    category = (data or {}).get("category") or "Water"
    prompt = f"[Current analysis category: {category}]\n{question}"

    try:
        # llm.chat() is a blocking call, and on-device inference can take a
        # noticeable moment — running it in the default executor keeps a slow
        # response from stalling every other socket handler in the meantime.
        loop = asyncio.get_event_loop()
        answer = await loop.run_in_executor(None, llm.chat, prompt)
    except Exception as e:
        print("chat_send LLM call failed:", e)
        answer = f"Local LLM error: {e}"

    await ui.sio.emit('chatResponse', {"content": answer}, room=sid)


@ui.sio.on('get_maintenance_status')
async def handle_get_maintenance_status(sid, data=None):
    await ui.sio.emit('maintenanceStatus', compute_calibration_health(), room=sid)


@ui.sio.on('get_analysis')
async def handle_analysis(sid, data=None):
    print(">>> ANALYSIS FIRED", data, flush=True)

    category = (data or {}).get("category")
    if category is None:
        category = "Other"

    measurements = [dict(r) for r in db.read("measurement")]
    profile = get_active_profile(category)
    model = get_active_model(category)

    rows = [m for m in measurements if str(m.get("category")) == str(category)]
    print(f">>> {len(rows)} rows in {category}", flush=True)

    if profile:
        means = np.asarray(json.loads(profile["channel_means"]), dtype=float)
        stds = np.asarray(json.loads(profile["channel_stds"]), dtype=float)
    else:
        # No Build Reference has been run yet for this category — fall back
        # to computing an ad-hoc mean/std directly from whatever reference-
        # flagged rows exist, so deviation scoring still works before the
        # operator has formally built a profile.
        refs = [normalize_spectrum(json.loads(m["raw_counts"])) for m in rows if int(m.get("is_reference", 0)) == 1]
        means = stds = None
        if len(refs) >= 2:
            arr = np.vstack([r for r in refs if r is not None])
            means = arr.mean(axis=0)
            stds = np.maximum(arr.std(axis=0, ddof=1), 1e-6)

    out = []
    for m in rows:
        arr = normalize_spectrum(json.loads(m.get("raw_counts", "[]")))
        if arr is None:
            continue
        pred = None
        conf = None
        if model:
            pred, conf = predict_with_model(model, arr)

        dev, status = compute_dev_status(m.get("known_value"), means, stds, arr, model, pred)

        out.append({
            "id": m["id"],
            "name": m["name"],
            "category": m["category"],
            "dev": dev,
            "pred": None if pred is None else round(float(pred), 3),
            "conf": None if conf is None else round(float(conf), 3),
            "status": status,
            "is_reference": int(m.get("is_reference", 0)),
        })

    print(">>> emitting", len(out), "rows", flush=True)
    await ui.sio.emit('analysisData', out, room=sid)


def loop():
    pass


App.run(user_loop=loop)