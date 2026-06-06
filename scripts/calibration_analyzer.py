"""
calibration_analyzer.py
-----------------------
Measure occupancy-estimate accuracy and, crucially, diagnose WHICH sensor signal
(if any) actually separates occupancy levels.

Reads data/calibration_log.csv (from calibration_logger.py) and reports:
  * exact-match accuracy and mean absolute error
  * over- vs under-counting
  * for each candidate signal (presence, n_persons, motion-rate): the value by
    actual occupancy, plus a verdict on whether it SEPARATES empty from occupied
  * a threshold suggestion only if presence is actually usable

Implausible actual counts (> MAX_PLAUSIBLE, e.g. a "22" typo) are ignored.

Usage:  python calibration_analyzer.py
"""

import csv
import os
from statistics import mean, median

DATA = os.path.join(os.path.dirname(__file__), "..", "data")
LOG = os.path.join(DATA, "calibration_log.csv")
MAX_PLAUSIBLE = 10   # actual_count above this is treated as a typo and dropped


def load():
    if not os.path.exists(LOG):
        return []
    with open(LOG) as f:
        return list(csv.DictReader(f))


def num(x, default=0.0):
    try:
        return float(x)
    except (TypeError, ValueError):
        return default


def to_bool(x):
    return str(x).strip().lower() in ("true", "1", "yes")


def by_count(rows, field, is_bool=False):
    """Group a field's values by actual occupancy count."""
    out = {}
    for r in rows:
        a = int(num(r["actual_count"]))
        val = (1 if to_bool(r.get(field)) else 0) if is_bool else num(r.get(field))
        out.setdefault(a, []).append(val)
    return out


def report_signal(name, grouped, as_rate=False):
    """Print a signal's value per occupancy and judge whether it separates."""
    print(f"\n{name} by actual occupancy:")
    summary = {}
    for a in sorted(grouped):
        vals = grouped[a]
        stat = mean(vals) if as_rate else median(vals)
        summary[a] = stat
        unit = "%" if as_rate else ""
        shown = f"{stat * 100:.0f}{unit}" if as_rate else f"{stat:.2f}"
        label = "rate" if as_rate else "median"
        print(f"  {a} people: {label} = {shown}  (n={len(vals)})")

    # Verdict: does empty (0) read LOWER than occupied (1)? If not, unusable.
    if 0 in summary and 1 in summary:
        if summary[0] >= summary[1]:
            print(f"  --> NOT USABLE: empty ({summary[0]:.2f}) reads >= 1-person "
                  f"({summary[1]:.2f}); this signal does not track occupancy.")
            return False
        print(f"  --> usable: empty < 1-person, separation exists.")
        return True
    print("  --> need samples at both 0 and 1 people to judge.")
    return None


def main():
    raw = load()
    rows = []
    dropped = 0
    for r in raw:
        if r.get("actual_count") in (None, "") or r.get("predicted_count") in (None, ""):
            continue
        if int(num(r["actual_count"])) > MAX_PLAUSIBLE:
            dropped += 1
            continue
        rows.append(r)

    if not rows:
        print(f"No usable data at {LOG}. Run calibration_logger.py first.")
        return

    actual = [int(num(r["actual_count"])) for r in rows]
    pred = [int(num(r["predicted_count"])) for r in rows]
    n = len(rows)

    exact = sum(1 for a, p in zip(actual, pred) if a == p)
    within1 = sum(1 for a, p in zip(actual, pred) if abs(a - p) <= 1)
    mae = mean(abs(a - p) for a, p in zip(actual, pred))
    over = sum(1 for a, p in zip(actual, pred) if p > a)
    under = sum(1 for a, p in zip(actual, pred) if p < a)

    print("=" * 52)
    print("  Occupancy calibration report")
    print("=" * 52)
    print(f"Samples              : {n}" + (f"  ({dropped} implausible dropped)" if dropped else ""))
    print(f"Exact-match accuracy : {exact / n * 100:.1f}%")
    print(f"Within +/-1 person   : {within1 / n * 100:.1f}%")
    print(f"Mean absolute error  : {mae:.2f} people")
    print(f"Overcounting         : {over / n * 100:.1f}%")
    print(f"Undercounting        : {under / n * 100:.1f}%")

    # ── Which signal actually separates occupancy? ──
    presence_ok = report_signal("Presence score", by_count(rows, "presence_score"))
    report_signal("CSI n_persons", by_count(rows, "n_persons"))
    report_signal("Motion detection", by_count(rows, "motion", is_bool=True), as_rate=True)

    print("\n" + "-" * 52)
    if presence_ok:
        emp = median(by_count(rows, "presence_score").get(0, [0]))
        one = median(by_count(rows, "presence_score").get(1, [0]))
        print(f"Suggested PRESENCE_OCCUPIED ~= {(emp + one) / 2:.2f}")
        print("Apply it in backend/.env, then restart the backend.")
    else:
        print("DIAGNOSIS: no signal cleanly separates empty from occupied.")
        print("Threshold tuning cannot fix this — the problem is upstream in the")
        print("CSI sensing itself. Check, in order:")
        print("  1. Was the backend+bridge RESTARTED with the consensus changes")
        print("     before logging? If not, re-log after restarting.")
        print("  2. RuView calibration: does it have an empty-room baseline step?")
        print("  3. Board placement: people must pass BETWEEN the CSI boards'")
        print("     signal paths, not sit off to the side.")


if __name__ == "__main__":
    main()
