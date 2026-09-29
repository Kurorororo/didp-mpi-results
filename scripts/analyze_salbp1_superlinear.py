#!/usr/bin/env python3
"""Count initial-bound matches and negative overhead among superlinear SALBP-1 runs.

Only the standard library and bundled data are needed.
Instance identities are (domain, problem), not run numbers.
"""

import math

from pathlib import Path
import sys

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.common import cutoff, records
from scripts.tables import solved_with_counters
from scripts.analyze_salbp1_initial_bounds import load_initial_bounds


def solved(row):
    return row.get("coverage") == 1 and row.get("invalid", 0) != 1


def counts(data, keys, bounds):
    superlinear = 0
    bound_matches_among_superlinear = 0
    negative_among_superlinear = 0
    for key in sorted(keys):
        baseline, target = data[96][key], data[1536][key]
        if baseline["optimal_cost"] != target["optimal_cost"]:
            raise ValueError(f"Conflicting optimal costs: {key}")
        for row in (baseline, target):
            for field in ("search_time", "expanded"):
                value = row.get(field)
                if value is None or not math.isfinite(value) or value < 0:
                    raise ValueError(f"Invalid {field}: {key}")
            if row["search_time"] == 0:
                raise ValueError(f"Zero search time: {key}")
        optimum = baseline["optimal_cost"]
        if optimum is None or not math.isfinite(optimum) or bounds[key] > optimum:
            raise ValueError(f"Invalid optimum or initial bound: {key}")
        # Strict inequalities: equal speedup/expansions do not qualify.
        if baseline["search_time"] > 16 * target["search_time"]:
            superlinear += 1
            bound_matches_among_superlinear += bounds[key] == optimum
            negative_among_superlinear += target["expanded"] < baseline["expanded"]
    return (len(keys), superlinear, negative_among_superlinear,
            bound_matches_among_superlinear)


def main():
    results = {
        "All paired optimal solves (no runtime cutoff)": [],
        "Paper cohort (96-core search time >=10 seconds)": [],
    }
    for algorithm in ("acps", "apps"):
        data = {p: records("salbp-1", algorithm, p) for p in (96, 768, 1536)}
        bounds = load_initial_bounds(set(data[96]))
        paired = {
            key
            for key in data[96].keys() & data[1536].keys()
            if solved(data[96][key]) and solved(data[1536][key])
        }
        # Match scripts.tables.anytime: valid counters and optimal solves at
        # all three core counts, using this algorithm's own 96-core cutoff.
        paper = {
            key
            for key in data[96]
            if cutoff(data[96][key])
            and all(solved_with_counters(data[p].get(key), p) for p in data)
        }
        for rows, keys in zip(results.values(), (paired, paper)):
            rows.append((algorithm.upper(), *counts(data, keys, bounds)))

    print("Superlinear: search_time[96] > 16 * search_time[1536].")
    print("Negative overhead: expanded[1536] < expanded[96].")
    print("Initial-bound match: HAC-1 dual_bound_progress[0][1] == optimal cost.")
    for title, rows in results.items():
        print(f"\n{title}\n")
        print(
            "| Algorithm | Compared instances | Superlinear | Also negative overhead | Also initial bound matches |"
        )
        print("|---|---:|---:|---:|---:|")
        for row in rows:
            print("| " + " | ".join(map(str, row)) + " |")


if __name__ == "__main__":
    main()
