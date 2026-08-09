#!/usr/bin/env python3
# seed_test_data.py — inject synthetic rows into an existing .db
# Usage:  python3 seed_test_data.py /path/to/edgeaispectrophotometer.db

import json, sqlite3, random, sys
from datetime import datetime, timedelta

DB = sys.argv[1] if len(sys.argv) > 1 else "edgeaispectrophotometer.db"

random.seed(42)
N_CH = 12

# White LED through distilled water — peaks near 555nm, dies past 700nm
WHITE = [8200, 11400, 15800, 21300, 32100, 41500, 38200, 29400, 18100, 7300, 2400, 980]
DARK  = [142, 138, 145, 151, 149, 156, 148, 143, 139, 141, 137, 144]
DSTD  = [3.8, 3.5, 4.1, 4.3, 4.0, 4.6, 4.2, 3.9, 3.7, 3.6, 3.4, 3.9]

conn = sqlite3.connect(DB)
conn.row_factory = sqlite3.Row
cur = conn.cursor()

t0 = datetime.now() - timedelta(hours=3)

# ---------------- baseline ----------------
cur.execute("""INSERT INTO baseline
    (created_at, raw_counts, dark_counts, dark_std, n_burst, is_active)
    VALUES (?,?,?,?,?,?)""",
    (t0.isoformat(timespec="seconds"), json.dumps(WHITE),
     json.dumps(DARK), json.dumps(DSTD), 10, 1))
bid = cur.lastrowid
print(f"baseline id {bid}")


def counts_for(absv, noise=0.006):
    """Invert Beer-Lambert into plausible raw ADC counts."""
    out = []
    for i in range(N_CH):
        a = max(absv[i] + random.gauss(0, noise), 0)
        t = 10 ** (-a)
        v = DARK[i] + (WHITE[i] - DARK[i]) * t
        out.append(int(round(v + random.gauss(0, DSTD[i]))))
    return out


n = 0
def add(name, cat, absv, known, is_ref, minutes):
    global n
    cur.execute("""INSERT INTO measurement
        (created_at, name, category, baseline_id, raw_counts,
         saturated, is_reference, known_value)
        VALUES (?,?,?,?,?,?,?,?)""",
        ((t0 + timedelta(minutes=minutes)).isoformat(timespec="seconds"),
         name, cat, bid, json.dumps(counts_for(absv)),
         0, int(is_ref), known))
    n += 1


def series(cat, shape, ref_abs, ref_n, levels, peak_abs, max_level, t_start, expo=1.0):
    for i in range(ref_n):
        add(f"{cat}_ref_{i+1:02d}", cat, [ref_abs * s for s in shape],
            0.0, True, t_start + i * 2)

    order = [(lvl, rep) for lvl in levels for rep in "abc"]
    random.shuffle(order)                      # randomized, like real collection
    for k, (lvl, rep) in enumerate(order):
        scale = peak_abs * (lvl / max_level) ** expo
        add(f"{cat}_{lvl}_{rep}", cat, [scale * s for s in shape],
            float(lvl), False, t_start + ref_n * 2 + k * 2)


# WATER — dye 0-20 %, cleanest Beer-Lambert case, peaks ~640nm
series("Water", [0.08, 0.11, 0.18, 0.31, 0.52, 0.74, 0.91, 1.00, 0.86, 0.24, 0.05, 0.02],
       ref_abs=0.004, ref_n=8, levels=(4, 8, 12, 16, 20),
       peak_abs=1.10, max_level=20, t_start=0)

# COFFEE — dissolved solids 0-10 g/L, broad absorption rising toward blue
series("Coffee", [1.00, 0.94, 0.82, 0.68, 0.47, 0.33, 0.24, 0.17, 0.12, 0.06, 0.03, 0.02],
       ref_abs=0.006, ref_n=6, levels=(2, 4, 6, 8, 10),
       peak_abs=1.60, max_level=10, t_start=80)

# MILK — 0-50 % added water; scattering-dominated, mildly nonlinear
MILK = [1.00, 0.96, 0.90, 0.84, 0.74, 0.66, 0.59, 0.52, 0.45, 0.36, 0.27, 0.22]
for i in range(8):
    add(f"Milk_ref_{i+1:02d}", "Milk", [1.42 * s for s in MILK], 0.0, True, 160 + i * 2)

order = [(lvl, rep) for lvl in (10, 20, 30, 40, 50) for rep in "abc"]
random.shuffle(order)
for k, (lvl, rep) in enumerate(order):
    scale = 1.42 * (1 - lvl / 100) ** 1.15
    add(f"Milk_{lvl}_{rep}", "Milk", [scale * s for s in MILK], float(lvl), False, 180 + k * 2)

# OTHER — unlabeled, exercises the null Dev/Pred/Conf path
add("Tap_water_01", "Other", [0.02] * N_CH, None, False, 250)
add("Olive_oil_01", "Other",
    [0.9, 0.7, 0.5, 0.35, 0.2, 0.12, 0.08, 0.06, 0.05, 0.04, 0.03, 0.03],
    None, False, 254)

# Deliberate anomaly — should score REJECT, predict ~25-30 %
add("Milk_ADULTERATED_unknown", "Milk", [0.61 * s for s in MILK], None, False, 260)

conn.commit()

for row in cur.execute("""SELECT category, COUNT(*) n,
                                 SUM(is_reference) refs,
                                 COUNT(known_value) labeled
                          FROM measurement GROUP BY category"""):
    print(f"  {row['category']:8} {row['n']:3} rows  {row['refs']} refs  {row['labeled']} labeled")

print(f"\ninserted 1 baseline + {n} measurements into {DB}")
conn.close()