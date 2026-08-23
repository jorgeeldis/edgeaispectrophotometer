#!/usr/bin/env python3

# seed_data.py — inject synthetic test rows into an existing .db
#
# python3 seed_data.py             append
# python3 seed_data.py --clear     delete all rows first

import json
import os
import sqlite3
import random
import sys
from datetime import datetime, timedelta

# Positional DB path, ignoring flags like --clear so "seed_data.py --clear"
# (no explicit path) correctly falls back to the default filename instead of
# treating "--clear" itself as the path.
_positional = [a for a in sys.argv[1:] if not a.startswith("--")]
DB = _positional[0] if _positional else "edgeaispectrophotometer.db"
CLEAR = "--clear" in sys.argv

if not os.path.exists(DB):
    print(f"Not found: {os.path.abspath(DB)}\n\nNearby .db files:")
    for root, _, files in os.walk("."):
        for f in files:
            if f.endswith(".db"):
                print("  ", os.path.join(root, f))
    sys.exit(1)

random.seed(42)

N_CH = 12

WAVELENGTHS = [
    405, 425, 450, 475, 515, 550,
    555, 600, 640, 690, 745, 855
]

# White LED through distilled water
# Used as the maximum/reference signal.
WHITE = [
    8200, 11400, 15800, 21300,
    32100, 40800, 41500, 38200,
    29400, 18100, 7300, 2400
]

# Dark measurement
DARK = [
    142, 138, 145, 151,
    149, 152, 156, 148,
    143, 139, 141, 137
]

DSTD = [
    3.8, 3.5, 4.1, 4.3,
    4.0, 4.4, 4.6, 4.2,
    3.9, 3.7, 3.6, 3.4
]


conn = sqlite3.connect(DB)
conn.row_factory = sqlite3.Row
cur = conn.cursor()


# ------------------------------------------------ CLEAR DATABASE

if CLEAR:
    for t in (
        "measurement",
        "baseline",
        "reference_profile",
        "model"
    ):
        try:
            cur.execute(f"DELETE FROM {t}")
            print(f"cleared {t} ({cur.rowcount} rows)")
        except sqlite3.OperationalError as e:
            print(f"skip {t}: {e}")

    try:
        cur.execute(
            "DELETE FROM sqlite_sequence "
            "WHERE name IN "
            "('measurement','baseline','reference_profile','model')"
        )
    except sqlite3.OperationalError:
        pass

    conn.commit()


t0 = datetime.now() - timedelta(hours=3)


# ------------------------------------------------ BASELINE

cur.execute(
    """
    INSERT INTO baseline
    (created_at, raw_counts, dark_counts, dark_std, n_burst, is_active)
    VALUES (?,?,?,?,?,?)
    """,
    (
        t0.isoformat(timespec="seconds"),
        json.dumps(WHITE),
        json.dumps(DARK),
        json.dumps(DSTD),
        10,
        1
    )
)

bid = cur.lastrowid

print(f"baseline id {bid}")


# ------------------------------------------------ HELPERS

def counts_for(absv, noise=0.006):
    """
    Generate normalized spectral values between 0 and 1.

    Beer-Lambert:
        transmission = 10^(-absorbance)

    The result is normalized to the white/dark calibration:

        normalized = (signal - dark) / (white - dark)

    Final values are clamped to [0, 1].
    """

    out = []

    for i in range(N_CH):

        # Add small measurement noise to absorbance
        a = max(
            absv[i] + random.gauss(0, noise),
            0
        )

        # Beer-Lambert transmission
        transmission = 10 ** (-a)

        # Convert transmission to a simulated ADC signal
        signal = (
            DARK[i]
            + (WHITE[i] - DARK[i]) * transmission
        )

        # Add detector noise
        signal += random.gauss(0, DSTD[i])

        # Normalize using dark/white references
        normalized = (
            signal - DARK[i]
        ) / (
            WHITE[i] - DARK[i]
        )

        # Guarantee 0 <= value <= 1
        normalized = max(0.0, min(1.0, normalized))

        out.append(round(normalized, 6))

    return out


n = 0


def add(name, cat, absv, known, is_ref, minutes):
    global n

    values = counts_for(absv)

    cur.execute(
        """
        INSERT INTO measurement
        (created_at, name, category, baseline_id, raw_counts,
         saturated, is_reference, known_value)
        VALUES (?,?,?,?,?,?,?,?)
        """,
        (
            (
                t0 + timedelta(minutes=minutes)
            ).isoformat(timespec="seconds"),

            name,
            cat,
            bid,

            # Values are now stored between 0 and 1
            json.dumps(values),

            0,
            int(is_ref),
            known
        )
    )

    n += 1


def series(
    cat,
    shape,
    ref_abs,
    ref_n,
    levels,
    peak_abs,
    max_level,
    t_start,
    expo=1.0
):
    # Reference measurements
    for i in range(ref_n):
        add(
            f"{cat}_ref_{i+1:02d}",
            cat,
            [ref_abs * s for s in shape],
            0.0,
            True,
            t_start + i * 2
        )

    # Randomized samples
    order = [
        (lvl, rep)
        for lvl in levels
        for rep in "abc"
    ]

    random.shuffle(order)

    for k, (lvl, rep) in enumerate(order):

        scale = (
            peak_abs
            * (lvl / max_level) ** expo
        )

        add(
            f"{cat}_{lvl}_{rep}",
            cat,
            [scale * s for s in shape],
            float(lvl),
            False,
            t_start + ref_n * 2 + k * 2
        )


# ------------------------------------------------ WATER
# Dye, 0-20% of stock
# Clean Beer-Lambert case, dye peaks ~640nm

series(
    "Water",

    [
        0.08, 0.11, 0.18, 0.31,
        0.52, 0.71, 0.74, 0.91,
        1.00, 0.86, 0.24, 0.05
    ],

    ref_abs=0.004,
    ref_n=8,

    levels=(4, 8, 12, 16, 20),

    peak_abs=1.10,
    max_level=20,

    t_start=0
)


# ------------------------------------------------ COFFEE
# Solids, 0-10 g/L
# Broad absorption rising toward blue

series(
    "Coffee",

    [
        1.00, 0.94, 0.82, 0.68,
        0.47, 0.35, 0.33, 0.24,
        0.17, 0.12, 0.06, 0.03
    ],

    ref_abs=0.006,
    ref_n=6,

    levels=(2, 4, 6, 8, 10),

    peak_abs=1.60,
    max_level=10,

    t_start=80
)


# ------------------------------------------------ MILK
# 0-50% added water
# Scattering-dominated

MILK = [
    1.00, 0.96, 0.90, 0.84,
    0.74, 0.67, 0.66, 0.59,
    0.52, 0.45, 0.36, 0.27
]


for i in range(8):
    add(
        f"Milk_ref_{i+1:02d}",
        "Milk",
        [1.42 * s for s in MILK],
        0.0,
        True,
        160 + i * 2
    )


order = [
    (lvl, rep)
    for lvl in (10, 20, 30, 40, 50)
    for rep in "abc"
]

random.shuffle(order)


for k, (lvl, rep) in enumerate(order):

    scale = (
        1.42
        * (1 - lvl / 100) ** 1.15
    )

    add(
        f"Milk_{lvl}_{rep}",
        "Milk",
        [scale * s for s in MILK],
        float(lvl),
        False,
        180 + k * 2
    )


# ------------------------------------------------ OTHER

add(
    "Tap_water_01",
    "Other",
    [0.02] * N_CH,
    None,
    False,
    250
)

add(
    "Olive_oil_01",
    "Other",
    [
        0.9, 0.7, 0.5, 0.35,
        0.2, 0.13, 0.12, 0.08,
        0.06, 0.05, 0.04, 0.03
    ],
    None,
    False,
    254
)


# ------------------------------------------------ DELIBERATE ANOMALY

add(
    "Milk_ADULTERATED_unknown",
    "Milk",
    [0.61 * s for s in MILK],
    None,
    False,
    260
)


# ------------------------------------------------ COMMIT

conn.commit()


# ------------------------------------------------ SUMMARY

print()

for r in cur.execute(
    """
    SELECT
        category,
        COUNT(*) n,
        SUM(is_reference) refs,
        COUNT(known_value) labeled
    FROM measurement
    GROUP BY category
    ORDER BY category
    """
):
    print(
        f"  {r['category']:8} "
        f"{r['n']:3} rows   "
        f"{r['refs']} refs   "
        f"{r['labeled']} labeled"
    )


print(
    f"\ninserted 1 baseline + {n} measurements into {DB}"
)


# ------------------------------------------------ VERIFY RANGE

print("\nChecking stored value ranges...")

valid = True

for r in cur.execute(
    "SELECT id, name, raw_counts FROM measurement"
):
    values = json.loads(r["raw_counts"])

    if any(v < 0 or v > 1 for v in values):
        print(
            f"WARNING: measurement {r['id']} "
            f"({r['name']}) contains values outside [0, 1]"
        )
        valid = False

if valid:
    print("OK: all measurement spectral values are between 0 and 1.")


conn.close()