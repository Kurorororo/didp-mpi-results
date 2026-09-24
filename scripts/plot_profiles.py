"""Render the expansion heatmaps and MPI timing breakdown."""
import csv
import math

import matplotlib.pyplot as plt
from matplotlib.colors import LogNorm
import numpy as np

from .common import DATA, PLOTS
from . import mpi


def read_trace(path):
    with path.open(newline="") as stream:
        records = list(csv.DictReader(stream))
    depth = np.array([int(row["depth"]) for row in records])
    f = np.array([int(row["f_value"]) for row in records])
    count = np.array([int(row["expanded"]) for row in records], dtype=np.int64)
    if len(records) == 0 or np.any(count <= 0):
        raise ValueError(f"Empty trace or nonpositive counts: {path}")
    return {"depth": depth, "f": f, "count": count}


def short_count(value):
    if value >= 1e9:
        return f"{value / 1e9:.2f}B"
    if value >= 1e6:
        return f"{value / 1e6:.2f}M"
    return f"{value / 1e3:.0f}k"


def failure_modes():
    plt.rcParams.update({
        "font.family": "DejaVu Sans",
        "font.size": 8,
        "axes.labelsize": 8,
        "axes.titlesize": 8,
        "xtick.labelsize": 7,
        "ytick.labelsize": 7,
        "axes.linewidth": 0.5,
        "xtick.major.width": 0.5,
        "ytick.major.width": 0.5,
        "xtick.major.size": 2.5,
        "ytick.major.size": 2.5,
        "pdf.fonttype": 42,
    })
    # Explicit edges put integer f values at row centers, including empty
    # f=139 cells in HAC. Identical edges are used by all panels in a row.
    cases = [
        {
            "directory": "tsptw-35",
            "label": "TSPTW · n100w140.001",
            "algorithms": ("acps", "apps", "hac"),
            "x_edges": np.arange(-0.5, 100, 1),
            "f_edges": np.arange(230, 771, 10),
            "xticks": [0, 25, 50, 75, 99],
            "yticks": [250, 500, 750],
        },
        {
            "directory": "salbp-1-1426",
            "label": "SALBP-1 · n=1000_22",
            "algorithms": ("acps", "apps", "hac"),
            "x_edges": np.arange(-0.5, 1140, 20),
            "f_edges": np.arange(136.5, 140, 1),
            "xticks": [0, 400, 800, 1136],
            "yticks": [137, 138, 139],
        },
    ]
    # Three algorithm columns retain the original figure width and height.
    fig = plt.figure(figsize=(6.8, 3.15))
    grid = fig.add_gridspec(
        2, 4, left=0.085, right=0.9, bottom=0.115, top=0.88,
        width_ratios=[1, 1, 1, 0.0525], hspace=0.88, wspace=0.22,
    )
    cmap = plt.get_cmap("viridis").copy()
    cmap.set_bad("white")
    for row_index, case in enumerate(cases):
        traces, histograms = [], []
        for algorithm in case["algorithms"]:
            path = DATA / "expansion-statistics" / case["directory"] / f"{algorithm}-768.csv"
            trace = read_trace(path)
            x, f, count = trace["depth"], trace["f"], trace["count"]
            histogram, _, _ = np.histogram2d(
                f, x,
                bins=[case["f_edges"], case["x_edges"]],
                weights=count,
            )
            # A shared-axis change must never clip or discard observations.
            assert int(histogram.sum()) == int(count.sum()), path
            traces.append(trace)
            histograms.append(histogram)
        upper = 10 ** math.ceil(math.log10(max(h.max() for h in histograms)))
        norm = LogNorm(vmin=1, vmax=upper)
        shared_axis = None
        for col, (algorithm, trace, histogram) in enumerate(
            zip(case["algorithms"], traces, histograms)
        ):
            ax = fig.add_subplot(grid[row_index, col], sharex=shared_axis, sharey=shared_axis)
            if shared_axis is None:
                shared_axis = ax
            mesh = ax.pcolormesh(
                case["x_edges"], case["f_edges"],
                np.ma.masked_equal(histogram, 0),
                cmap=cmap, norm=norm, shading="flat",
                rasterized=True, antialiased=False,
            )
            ax.set_xlim(case["x_edges"][0], case["x_edges"][-1])
            ax.set_ylim(case["f_edges"][0], case["f_edges"][-1])
            ax.set_xticks(case["xticks"])
            ax.set_yticks(case["yticks"])
            ax.set_xlabel("Depth", labelpad=1)
            if col == 0:
                ax.set_ylabel("$f$", rotation=0, labelpad=6)
            else:
                ax.tick_params(axis="y", labelleft=False, left=False)
            count = trace["count"]
            ax.set_title(f"{algorithm.upper()}  ·  {short_count(int(count.sum()))}", pad=3)
        cax = fig.add_subplot(grid[row_index, 3])
        ticks = [1, 10 ** (int(math.log10(upper)) // 2), upper]
        colorbar = fig.colorbar(mesh, cax=cax, ticks=ticks)
        colorbar.ax.set_ylabel("Expansions/bin", fontsize=7, labelpad=3)
        colorbar.ax.tick_params(labelsize=7, pad=2)
        colorbar.outline.set_linewidth(0.4)
        bounds = shared_axis.get_position()
        fig.text(
            bounds.x0, bounds.y1 + 0.062, case["label"],
            fontsize=8, fontweight="bold", ha="left", va="bottom",
        )
    fig.savefig(PLOTS / "failure-modes.pdf", dpi=400)
    plt.close(fig)


GROUPS = {
    "Non-MPI": ("non_mpi_search",),
    "MPI_Bsend": ("MPI_Bsend",),
    "MPI_Recv": ("MPI_Recv",),
    "MPI_Iprobe": ("MPI_Iprobe_hit", "MPI_Iprobe_miss"),
    "Other MPI": ("MPI_Send", "MPI_Barrier", "MPI_Gather"),
}


COLORS = ("#648BA8", "#D55E00", "#009E73", "#CC79A7", "#777777")


def mpi_breakdown():
    configs = mpi.load_configurations(DATA / "mpi-timing")
    plt.rcParams.update({"font.size": 10, "axes.spines.top": False, "axes.spines.right": False,
                         "pdf.fonttype": 42})
    fig, ax = plt.subplots(figsize=(5.2, 3.7))
    fig.subplots_adjust(left=0.15, right=0.985, bottom=0.19, top=0.80)
    breakdown = []
    positions = [i * 1.35 for i in range(len(configs))]
    for i, c in zip(positions, configs):
        positive = negative = 0
        values = []
        outside_labels = []
        for (name, operations), color in zip(GROUPS.items(), COLORS):
            value = sum(mpi.total(c, op) for op in operations) / c["props"]["expanded"] / 1000
            values.append(value)
            bottom = positive if value >= 0 else negative
            ax.bar(i, value, bottom=bottom, width=0.58,
                   color=color, edgecolor="white", linewidth=0.35, label=name if i == 0 else None)
            center = bottom + value / 2
            if 0 < abs(value) < 0.001:
                exponent = math.floor(math.log10(abs(value)))
                number = rf"${value / 10**exponent:.2f}\times10^{{{exponent}}}$"
            elif 0 < abs(value) < 0.01:
                number = f"{value:.4f}"
            else:
                number = f"{value:.2f}"
            gid = f"category-value-{c['id']}-{name.replace(' ', '-')}"
            if abs(value) >= 6:
                ax.text(i, center, number, ha="center", va="center", fontsize=9, gid=gid)
            else:
                outside_labels.append((center, number, color, gid))
            if value >= 0:
                positive += value
            else:
                negative += value
            breakdown.append(dict(configuration=c["id"], category=name, rank_us_per_expansion=value))
        # Separate labels for narrow segments without changing their heights.
        spacing = 5.5
        label_center = sum(row[0] for row in outside_labels) / len(outside_labels)
        for j, (center, number, color, gid) in enumerate(outside_labels):
            y = label_center + (j - (len(outside_labels) - 1) / 2) * spacing
            ax.plot([i + 0.29, i + 0.35, i + 0.40], [center, y, y], color=color, linewidth=0.8)
            ax.text(i + 0.43, y, number, ha="left", va="center", fontsize=8, gid=gid)
        reference = mpi.total(c, "search_total") / c["props"]["expanded"] / 1000
        assert math.isclose(sum(values), reference, rel_tol=1e-10)
    ax.set_xticks(positions, [f"{c['processes']:,} cores\n{c['nodes']} machine{'s' if c['nodes'] != 1 else ''}"
                             for c in configs], fontsize=9)
    ax.set_xlim(-0.48, positions[-1] + 0.97)
    ax.set_ylabel("Time per expansion (µs)")
    ax.set_axisbelow(True)
    ax.grid(axis="y", color="#dddddd", linewidth=0.6)
    ax.set_ylim(bottom=0)
    ax.set_ylim(top=max(sum(row["rank_us_per_expansion"] for row in breakdown
                           if row["configuration"] == c["id"]) for c in configs) * 1.08)
    handles, labels = ax.get_legend_handles_labels()
    order = [3, 1, 2, 4, 0]
    fig.legend([handles[i] for i in order], [labels[i] for i in order],
               loc="upper center", bbox_to_anchor=(0.55, 0.99), ncol=3, frameon=False, fontsize=8)
    fig.savefig(PLOTS / "mpi-breakdown.pdf", dpi=200, facecolor="white")
    plt.close(fig)
