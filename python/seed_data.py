# seed_data.py — synthetic dataset for testing Analysis before real samples exist
import json, math, random
from datetime import datetime, timedelta

random.seed(42)   # reproducible

N_CH = 12
WAVELENGTHS = [405, 425, 450, 475, 515, 555, 600, 640, 690, 745, 855, 940]

# White LED through distilled water — peaks near 555nm, falls off past 700nm
WHITE = [8200, 11400, 15800, 21300, 32100, 41500, 38200, 29400, 18100, 7300, 2400, 980]
DARK  = [142, 138, 145, 151, 149, 156, 148, 143, 139, 141, 137, 144]
DSTD  = [3.8, 3.5, 4.1, 4.3, 4.0, 4.6, 4.2, 3.9, 3.7, 3.6, 3.4, 3.9]


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

def seed(db, clear=False):
    if clear:
        for t in ("measurement", "baseline", "reference_profile", "model"):
            try:
                db.drop_table(t)
            except Exception:
                pass
        db.create_table("baseline", columnsBaseline)
        db.create_table("measurement", columnsMeasurement)
        db.create_table("reference_profile", columnsProfile)
        db.create_table("model", columnsModel)

    t0 = datetime.now() - timedelta(hours=3)

    # ---- baseline ----
    db.store("baseline", {
        "created_at": t0.isoformat(timespec="seconds"),
        "raw_counts": json.dumps(WHITE),
        "dark_counts": json.dumps(DARK),
        "dark_std": json.dumps(DSTD),
        "n_burst": 10,
        "is_active": 1,
    })
    bid = max(dict(r)["id"] for r in db.read("baseline"))

    def counts_for(absorbance_vec, noise=0.006):
        """Invert Beer-Lambert to produce plausible raw ADC counts."""
        out = []
        for i in range(N_CH):
            a = max(absorbance_vec[i] + random.gauss(0, noise), 0)
            t = 10 ** (-a)                                   # transmittance
            v = DARK[i] + (WHITE[i] - DARK[i]) * t
            out.append(int(round(v + random.gauss(0, DSTD[i]))))
        return out

    n = 0

    def add(name, cat, absv, known, is_ref, minutes):
        nonlocal n
        db.store("measurement", {
            "created_at": (t0 + timedelta(minutes=minutes)).isoformat(timespec="seconds"),
            "name": name,
            "category": cat,
            "baseline_id": bid,
            "raw_counts": json.dumps(counts_for(absv)),
            "saturated": 0,
            "is_reference": int(is_ref),
            "known_value": known,
            "wavelengths": json.dumps(WAVELENGTHS),   # drop if not a column
        })
        n += 1

    # ---------------- WATER — dye, 0-20 % of stock ----------------
    # Cleanest case: pure Beer-Lambert, dye peaks ~630nm (channel 8)
    dye_shape = [0.08, 0.11, 0.18, 0.31, 0.52, 0.74, 0.91, 1.00, 0.86, 0.24, 0.05, 0.02]

    for i in range(8):                                        # references at 0 %
        add(f"Water_ref_{i+1:02d}", "Water",
            [0.004 * s for s in dye_shape], 0.0, True, i * 2)

    order = [(lvl, rep) for lvl in (4, 8, 12, 16, 20) for rep in "abc"]
    random.shuffle(order)                                     # randomized, as in real collection
    for k, (lvl, rep) in enumerate(order):
        add(f"Water_{lvl}_{rep}", "Water",
            [0.055 * lvl / 20 * 2.0 * s for s in dye_shape], float(lvl), False, 20 + k * 2)

    # ---------------- COFFEE — dissolved solids, 0-10 g/L ----------------
    # Broad absorption rising toward blue
    cof_shape = [1.00, 0.94, 0.82, 0.68, 0.47, 0.33, 0.24, 0.17, 0.12, 0.06, 0.03, 0.02]

    for i in range(6):
        add(f"Coffee_ref_{i+1:02d}", "Coffee",
            [0.006 * s for s in cof_shape], 0.0, True, 80 + i * 2)

    order = [(lvl, rep) for lvl in (2, 4, 6, 8, 10) for rep in "abc"]
    random.shuffle(order)
    for k, (lvl, rep) in enumerate(order):
        add(f"Coffee_{lvl}_{rep}", "Coffee",
            [0.16 * lvl / 10 * 1.6 * s for s in cof_shape], float(lvl), False, 95 + k * 2)

    # ---------------- MILK — scattering, 0-50 % added water ----------------
    # Scattering falls with wavelength; slight nonlinearity at low dilution
    milk_shape = [1.00, 0.96, 0.90, 0.84, 0.74, 0.66, 0.59, 0.52, 0.45, 0.36, 0.27, 0.22]

    for i in range(8):
        add(f"Milk_ref_{i+1:02d}", "Milk",
            [1.42 * s for s in milk_shape], 0.0, True, 160 + i * 2)

    order = [(lvl, rep) for lvl in (10, 20, 30, 40, 50) for rep in "abc"]
    random.shuffle(order)
    for k, (lvl, rep) in enumerate(order):
        frac = lvl / 100
        scale = 1.42 * (1 - frac) ** 1.15                     # mild nonlinearity
        add(f"Milk_{lvl}_{rep}", "Milk",
            [scale * s for s in milk_shape], float(lvl), False, 180 + k * 2)

    # ---------------- OTHER — unlabeled, tests the null path ----------------
    add("Tap_water_01", "Other", [0.02] * N_CH, None, False, 250)
    add("Olive_oil_01", "Other",
        [0.9, 0.7, 0.5, 0.35, 0.2, 0.12, 0.08, 0.06, 0.05, 0.04, 0.03, 0.03],
        None, False, 254)

    # ---------------- Deliberate anomaly — should score REJECT ----------------
    add("Milk_ADULTERATED_unknown", "Milk",
        [0.61 * s for s in milk_shape], None, False, 260)

    print(f">>> seeded 1 baseline + {n} measurements", flush=True)