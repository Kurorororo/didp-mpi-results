"""Render the four-panel rank-local memory figure."""
from dataclasses import dataclass
from pathlib import Path
import csv
import json
import math
import re

import matplotlib.pyplot as plt
from matplotlib.ticker import MaxNLocator
import numpy as np

from .common import DATA, PLOTS, source_path


GB = 10**9
MEMORY_REFERENCE_BYTES = 4 * GB
CASES = {"tsptw": "TSPTW", "salbp-1": "SALBP-1", "m-pdtsp": "m-PDTSP", "sualbp-2": "SUALBP-2"}
RSS = "resident_memory_bytes"
RETAINED = "estimated_retained_node_and_state_bytes"
TOTAL = "estimated_search_data_structure_bytes"
OPEN = "open_list_allocated_bytes"
CHAIN = "transition_chain_allocated_bytes"
ESTIMATE_LABEL = "Estimated memory usage by states and related data structures"
MPI_BUFFER_BYTES = 1_000_000_000
MPI_BUFFER_LABEL = "MPI buffer capacity: 1 GB"
BLUE, ORANGE = "#0072B2", "#D55E00"


@dataclass
class Trace:
    problem: str
    run: int
    rank: int
    path: Path
    rows: list[dict]
    instance: str
    instance_domain: str

    @property
    def instance_label(self):
        name = Path(self.instance).stem
        # SUALBP-2 reuses instance filenames across setup-time variants.
        return f"{name} ({self.instance_domain})" if self.problem == "sualbp-2" else name

    @property
    def label(self):
        return CASES[self.problem]

    def values(self, key):
        return np.array([np.nan if r[key] is None else r[key] for r in self.rows], dtype=float)

    @property
    def times(self):
        return self.values("elapsed_time")


def read_memory_rows(path, rank):
    float_fields = {"elapsed_time", "estimated_search_data_structure_bytes_per_search_node"}
    with path.open(newline="") as stream:
        rows = [
            {k: None if v == "" else float(v) if k in float_fields else int(v)
             for k, v in r.items()}
            for r in csv.DictReader(stream)
        ]
    if not rows:
        raise ValueError(f"Empty trace: {path}")
    versions = {r.get("memory_estimate_version", 1) for r in rows}
    if len(versions) != 1 or not versions <= {1, 2}:
        raise ValueError(f"Mixed or unsupported memory estimate versions: {path}")
    version = next(iter(versions))
    for i, r in enumerate(rows):
        checks = {
            "finite nonnegative observations": all(v is None or (math.isfinite(v) and v >= 0) for v in r.values()),
            "rank matches filename": r["rank"] == rank,
            "positive RSS when observed": r[RSS] is None or r[RSS] > 0,
            "increasing elapsed time": i == 0 or rows[i-1]["elapsed_time"] < r["elapsed_time"],
            "registry = open + closed entries": r["registry_entries"] == r["registry_open_entries"] + r["registry_closed_entries"],
            "registry = inserted - removed": r["registry_entries"] == r["registry_inserted"] - r["registry_removed"],
            "total estimate = retained + open storage + chains": r[TOTAL] == r[RETAINED] + r[OPEN] + r[CHAIN],
        }
        if version == 1:
            checks["legacy retained = registry entries * nominal size"] = (
                r[RETAINED] == r["registry_entries"] * r["estimated_node_and_state_bytes_per_search_node"])
        else:
            checks.update({
                "live nodes = created - dropped": r["live_nodes"] == r["live_nodes_created"] - r["live_nodes_dropped"],
                "outside registry = live - registered": r["live_nodes_outside_registry"] == r["live_nodes"] - r["registry_entries"],
                "retained = private + shared + registry": r[RETAINED] == sum(r[k] for k in (
                    "estimated_private_node_and_resource_bytes", "estimated_shared_signature_bytes", "estimated_registry_storage_bytes")),
                "bytes per live node": r["estimated_search_data_structure_bytes_per_search_node"] is None if r["live_nodes"] == 0 else math.isclose(
                    r["estimated_search_data_structure_bytes_per_search_node"], r[TOTAL] / r["live_nodes"], rel_tol=1e-12),
            })
        for name, valid in checks.items():
            if not valid:
                raise ValueError(f"{path.name}, CSV line {i+2}: failed {name}")
    return rows


def read_traces():
    traces = []
    for problem in CASES:
        paths = sorted((DATA / "memory-statistics").glob(f"{problem}-run-*-memory_statistics_rank_*.csv"))
        if len(paths) != 1:
            raise ValueError(f"Expected one trace for {problem}, found {len(paths)}")
        path = paths[0]
        match = re.fullmatch(r"(.+)-run-(\d+)-memory_statistics_rank_(\d+)\.csv", path.name)
        run, rank = int(match[2]), int(match[3])
        rows = read_memory_rows(path, rank)
        metadata_path = source_path(problem, 'hac', 96)
        instances = {(r["domain"], r["problem"])
                     for r in json.loads(metadata_path.read_text()).values() if r["run"] == run}
        if len(instances) != 1:
            raise ValueError(f"Expected one instance for {problem} run {run}, found {instances}")
        instance_domain, instance = instances.pop()
        traces.append(Trace(problem, run, rank, path, rows, instance, instance_domain))
    return traces


def style_axis(ax):
    ax.grid(axis="y", color="#dddddd", linewidth=0.5, zorder=0)
    ax.spines[["top", "right"]].set_visible(False)
    ax.tick_params(length=2.5)


def draw_memory(trace, ax, memory_limit, mpi_buffer_bytes=0):
    t, rss, estimated = trace.times, trace.values(RSS) / GB, trace.values(TOTAL) / GB
    band = None
    if mpi_buffer_bytes:
        upper = estimated + mpi_buffer_bytes / GB
        band = ax.fill_between(t, estimated, upper, color="#777777", alpha=0.14,
                               linewidth=0, label=MPI_BUFFER_LABEL, zorder=1)
        ax.plot(t, upper, color="#777777", linestyle=":", linewidth=0.9, zorder=2)
    ax.axhline(MEMORY_REFERENCE_BYTES / GB, color="#666666", linestyle="--", linewidth=0.9, zorder=2)
    lines = ax.plot(t, rss, color=BLUE, linewidth=1.3, label="Resident set size (RSS)")
    lines += ax.plot(t, estimated, color=ORANGE, linewidth=1.3, linestyle="--", label=ESTIMATE_LABEL)
    ax.set_ylim(0, memory_limit)
    ax.set_yticks(np.arange(0, memory_limit + 0.01, 1))
    ax.set_xlabel("Elapsed time (s)", labelpad=2)
    ax.xaxis.set_major_locator(MaxNLocator(nbins=3, min_n_ticks=3, integer=True))
    ax.set_xlim(0, t[-1] * 1.06)
    # End markers keep an isolated final observation visible after a missing sample.
    for values, color in ((rss, BLUE), (estimated, ORANGE)):
        index = np.flatnonzero(np.isfinite(values))[-1]
        ax.plot(t[index], values[index], "o", color=color, markersize=2.5)
    style_axis(ax)
    return lines, band


def draw_overview(traces, memory_limit, mpi_buffer_bytes):
    height = 2.6 if mpi_buffer_bytes else 2.35
    fig = plt.figure(figsize=(7.4, height))
    # Preserve the panel sizes when adding the capacity-reference legend row.
    grid = fig.add_gridspec(1, 4, left=0.083, right=0.985, bottom=0.40 / height, top=1.645 / height,
                            wspace=0.18)
    for col, trace in enumerate(traces):
        ax = fig.add_subplot(grid[0, col])
        lines, band = draw_memory(trace, ax, memory_limit, mpi_buffer_bytes)
        ax.set_title(f"{trace.label}\n{trace.instance_label}", fontsize=8, pad=6)
        if col == 0:
            ax.set_ylabel("Memory (GB)", labelpad=4)
        else:
            ax.tick_params(labelleft=False)
    fig.legend(lines, [line.get_label() for line in lines], loc="upper center",
               bbox_to_anchor=(0.53, 0.985), ncol=2, frameon=False, fontsize=8)
    if band is not None:
        fig.legend([band], [band.get_label()], loc="upper center",
                   bbox_to_anchor=(0.53, 0.895), frameon=False, fontsize=7.5)
    fig.savefig(PLOTS / "memory-growth.pdf", dpi=300, metadata={"CreationDate": None, "ModDate": None})
    plt.close(fig)


def build():
    plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 8,
                         "axes.labelsize": 8, "axes.titlesize": 8,
                         "xtick.labelsize": 7, "ytick.labelsize": 7,
                         "axes.linewidth": 0.5, "pdf.fonttype": 42})
    draw_overview(read_traces(), 4.2, MPI_BUFFER_BYTES)
