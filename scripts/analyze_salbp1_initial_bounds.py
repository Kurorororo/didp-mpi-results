#!/usr/bin/env python3
"""Count matches between HAC-1 initial dual bounds and proven SALBP-1 optima."""

import json
import math
from pathlib import Path
import re
import sys

# Support both direct execution and python -m scripts.analyze_salbp1_initial_bounds.
if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.common import DATA, cutoff, records
from scripts.tables import solved_with_counters


def load_initial_bounds(keys):
    """Read HAC-1 bounds at zero expansions, aligned to the requested instances."""
    hac = records("salbp-1", "hac", 1)
    if set(hac) != keys:
        raise ValueError("HAC-1 instance set differs from ACPS/APPS results")
    bounds = {}
    for key, row in hac.items():
        progress = row.get("dual_bound_progress")
        if not progress or len(progress[0]) != 3 or progress[0][2] != 0:
            raise ValueError(f"Missing initial bound at zero expansions: {key}")
        # Entries are [elapsed time, dual bound, expanded states].
        bound = progress[0][1]
        if bound is None or not math.isfinite(bound):
            raise ValueError(f"Invalid initial bound: {key}")
        bounds[key] = bound
    return bounds


def main():
    data = {(a, p): records("salbp-1", a, p)
            for a in ("acps", "apps") for p in (96, 768, 1536)}
    keys = set(data["acps", 96])
    if any(set(rows) != keys for rows in data.values()):
        raise ValueError("Configuration instance sets differ")
    bounds = load_initial_bounds(keys)

    # Independently check every bundled log that records an initial bound.
    checked = 0
    for log in sorted((DATA / "brfs-runs/salbp-1").glob("*/*/stdout.txt")):
        match = re.search(r"^Initial dual bound: (\d+)", log.read_text(), re.M)
        if match:
            meta = json.loads(log.with_name("static-properties.json").read_text())
            key = meta["domain"], meta["problem"]
            if bounds[key] != int(match[1]):
                raise ValueError(f"Initial bound differs from log: {log}")
            checked += 1

    solved = {ap: {key for key, row in rows.items()
                   if row.get("coverage") == 1 and row.get("invalid", 0) != 1}
              for ap, rows in data.items()}
    optima = {}
    for ap, cohort in solved.items():
        for key in cohort:
            cost = data[ap][key]["optimal_cost"]
            if cost is None or not math.isfinite(cost) or bounds[key] > cost:
                raise ValueError(f"Invalid optimum or bound: {ap}, {key}")
            if key in optima and optima[key] != cost:
                raise ValueError(f"Conflicting optimal costs: {key}")
            optima[key] = cost

    def report(label, cohort):
        matches = sum(bounds[key] == optima[key] for key in cohort)
        print(f"| {label} | {len(cohort)} | {matches} |")

    print("Initial bound: HAC-1 dual_bound_progress[0][1] (zero expansions).\n")
    print("| Configuration / cohort | Optimally solved instances | Initial bound matches |")
    print("|---|---:|---:|")
    for (a, p), cohort in solved.items():
        report(f"{a.upper()} / {p} cores", cohort)
    for a in ("acps", "apps"):
        report(f"{a.upper()} / any core count", set.union(
            *(solved[a, p] for p in (96, 768, 1536))))
    report("Either algorithm / any core count", set.union(*solved.values()))
    for a in ("acps", "apps"):
        report(f"{a.upper()} / paired 96 and 1536", solved[a, 96] & solved[a, 1536])
        paper = {key for key in keys if cutoff(data[a, 96][key])
                 and all(solved_with_counters(data[a, p].get(key), p)
                         for p in (96, 768, 1536))}
        report(f"{a.upper()} / paper >=10-second cohort", paper)
    print(f"\nValidated initial bounds against {checked} bundled logs.")


if __name__ == "__main__":
    main()
