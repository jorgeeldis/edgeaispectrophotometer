from arduino.app_utils import *
from arduino.app_bricks.web_ui import WebUI
from arduino.app_bricks.dbstorage_sqlstore import SQLStore
import numpy as np
import math
import json
import datetime
import pandas

ui = WebUI()

# Stores the latest spectrum received from Arduino
latest_hardware_data = []
baseline = []
lastScan = []
latest_baseline_id = None
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


def build_context(category=None):
    category = category or "Water"
    recent = [dict(r) for r in db.read("measurement")][-5:]
    profile = get_active_profile(category)
    if profile is None:
        for alt in ("Water", "Coffee", "Milk", "Other"):
            profile = get_active_profile(alt)
            if profile is not None:
                break
    model = get_active_model(category)
    if model is None:
        for alt in ("Water", "Coffee", "Milk", "Other"):
            model = get_active_model(alt)
            if model is not None:
                break
    health = compute_calibration_health()
    return {
        "recent_measurements": recent,
        "active_profile": profile,
        "model_metrics": model,
        "calibration_age_hours": health["dark_reference_age_hours"],
        "drift_percent": health["baseline_drift_percent"],
        "health_status": health["status"],
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
    conf = max(0.0, min(1.0, 1.0 / (1.0 + max(float(model.get("rmse", 0.0) or 0.0), 0.05))))
    return pred, round(conf, 4)


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

    lastScan = [math.log10(baseline[i] / latest_hardware_data[i]) for i in range(len(baseline))]

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
        measurement_id = db.store("measurement", {
            "created_at": data.get("created_at") or datetime.datetime.utcnow().isoformat(),
            "name": data.get("name"),
            "category": data.get("category"),
            "baseline_id": baseline_id,
            "raw_counts": json.dumps(data.get("raw_counts")),
            "saturated": int(data.get("saturated")),
            "is_reference": int(data.get("is_reference")),
            "known_value": data.get("known_value"),
        })

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
        db.store("reference_profile", {**row, "is_active": 0}, row.get("id"))

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
    await ui.sio.emit('sanityPlotResponse', {"success": r2 > 0.99, "category": category, "r2": round(r2, 4), "reason": reason}, room=sid)


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
        db.store("model", {**row, "is_active": 0}, row.get("id"))

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


@ui.sio.on('export_report')
async def handle_export_report(sid, data=None):
    category = (data or {}).get("category") or "Other"
    profile = get_active_profile(category)
    model = get_active_model(category)
    path = f"reports/{category.lower()}_{datetime.datetime.utcnow().strftime('%Y%m%d%H%M%S')}.html"
    report_id = db.store("report", {
        "created_at": datetime.datetime.utcnow().isoformat(),
        "category": category,
        "type": "PDF preview",
        "profile_id": profile.get("id") if profile else None,
        "model_id": model.get("id") if model else None,
        "path": path,
        "description": f"{category} report",
        "is_active": 1,
    })
    await ui.sio.emit('reportSaved', {"success": True, "report_id": report_id, "path": path, "category": category}, room=sid)
    await handle_get_reports(sid)


@ui.sio.on('chat_send')
async def handle_chat_send(sid, data=None):
    question = (data or {}).get("question", "").strip()
    if not question:
        await ui.sio.emit('chatResponse', {"content": "Please ask a question about the instrument, a sample, or a calibration step."}, room=sid)
        return

    category = (data or {}).get("category") or "Water"
    context = build_context(category)
    llm_available = False
    if llm_available:
        answer = "LLM execution is available here; context would be sent to the local model."
    else:
        answer = (
            "Local LLM is not available in this runtime. Based on current context: "
            f"{len(context['recent_measurements'])} recent scans are available, the active reference profile is {context['active_profile'].get('category') if context['active_profile'] else 'unset'}, "
            f"and the active model is {context['model_metrics'].get('category') if context['model_metrics'] else 'unset'}. "
            f"The current calibration status is {context['health_status']} and drift is {context['drift_percent']}%. "
            "Question: " + question
        )
    await ui.sio.emit('chatResponse', {"content": answer, "context": context}, room=sid)


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
        dev = None
        if means is not None and stds is not None:
            z = (arr - means) / stds
            dev = round(float(np.sqrt(np.mean(z ** 2))), 2)

        pred = None
        conf = None
        if model:
            pred, conf = predict_with_model(model, arr)

        out.append({
            "id": m["id"],
            "name": m["name"],
            "category": m["category"],
            "dev": dev,
            "pred": None if pred is None else round(float(pred), 3),
            "conf": None if conf is None else round(float(conf), 3),
            "status": (None if dev is None else "PASS" if dev < 2 else "ATTENTION" if dev < 3 else "REJECT"),
            "is_reference": int(m.get("is_reference", 0)),
        })

    print(">>> emitting", len(out), "rows", flush=True)
    await ui.sio.emit('analysisData', out, room=sid)


def loop():
    pass


App.run(user_loop=loop)