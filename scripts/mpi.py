"""Read and validate exclusive MPI timing and communication counters."""


import csv
import json
import math
import re


CONFIGS = (
    ("96p-1n", "tsptw-96-run12-sample100", 96, 1),
    ("96p-16n", "tsptw-96-16nodes-run12-sample100", 96, 16),
    ("1536p-16n", "tsptw-1536-run12-sample100", 1536, 16),
)


VOLUME_FIELDS = ("intra_node_messages", "intra_node_payload_bytes",
                 "inter_node_messages", "inter_node_payload_bytes")


PLACEMENT_FIELDS = ("node_leader_rank", "ranks_on_node")


OPERATIONS = {"search_total", "non_mpi_search", "MPI_Bsend", "MPI_Recv", "MPI_Iprobe_hit", "MPI_Iprobe_miss", "MPI_Send", "MPI_Barrier", "MPI_Gather"}


def communication_data(rows, processes):
    """Validate exact send counters and discovered topology; accept old CSVs."""
    fields = set(VOLUME_FIELDS + PLACEMENT_FIELDS)
    available = set(next(iter(rows.values()))) & fields
    if not available:
        return None
    require(available == fields, "Incomplete communication schema")
    placement = {}
    for rank in range(processes):
        row = rows[str(rank), "search_total"]
        leader, size = (int(row[key]) for key in PLACEMENT_FIELDS)
        require(0 <= leader < processes and 0 < size <= processes, "Invalid node placement")
        placement[rank] = (leader, size)
    leaders = sorted({leader for leader, _ in placement.values()})
    for leader in leaders:
        members = [rank for rank, (node, _) in placement.items() if node == leader]
        require(leader == min(members), "Node leader is not first group rank")
        require(all(placement[rank][1] == len(members) for rank in members), "Node rank-count mismatch")
    for (rank, op), row in rows.items():
        if rank == "all":
            require(all(row[k] == "" for k in PLACEMENT_FIELDS), "Aggregate has rank placement")
        else:
            require(tuple(int(row[k]) for k in PLACEMENT_FIELDS) == placement[int(rank)], "Inconsistent rank placement")
        if op not in {"MPI_Bsend", "MPI_Send"}:
            require(all(row[k] == "" for k in VOLUME_FIELDS), "Non-send operation has volume counters")
            continue
        values = {key: int(row[key]) for key in VOLUME_FIELDS}
        require(all(v >= 0 for v in values.values()), "Negative communication counter")
        require(values["intra_node_messages"] + values["inter_node_messages"] == row["calls"],
                "Locality counts do not equal send calls")
        for locality in ("intra_node", "inter_node"):
            require(values[locality + "_messages"] > 0 or values[locality + "_payload_bytes"] == 0,
                    "Payload bytes without messages")
        if len(leaders) == 1:
            require(values["inter_node_messages"] == values["inter_node_payload_bytes"] == 0,
                    "Inter-node traffic on one node")
        if rank == "all":
            for key in VOLUME_FIELDS:
                require(values[key] == sum(int(rows[str(r), op][key]) for r in range(processes)),
                        f"Communication aggregate mismatch: {key}")
    ranks = [dict(rank=rank, node_leader_rank=placement[rank][0], ranks_on_node=placement[rank][1],
                  **{key: sum(int(rows[str(rank), op][key]) for op in ("MPI_Bsend", "MPI_Send"))
                     for key in VOLUME_FIELDS}) for rank in range(processes)]
    totals = {key: sum(int(rows["all", op][key]) for op in ("MPI_Bsend", "MPI_Send")) for key in VOLUME_FIELDS}
    return dict(nodes=len(leaders), ranks=ranks, totals=totals)


def require(condition, message):
    if not condition:
        raise ValueError(message)


def close(a, b, tolerance=0.0011):
    return math.isclose(a, b, rel_tol=1e-12, abs_tol=tolerance)


def read_timing(path, processes):
    """Check counts, shared probe sampling, aggregation and signed accounting."""
    rows = {}
    with path.open(newline="") as stream:
        for raw in csv.DictReader(stream):
            rank, op = raw["rank"], raw["operation"]
            require(op in OPERATIONS, f"{path}: expected level-1 operation, got {op}")
            require((rank, op) not in rows, f"{path}: duplicate row {rank}/{op}")
            row = dict(raw)
            for key in ("calls", "timed_calls", "sampled_ns", "sample_interval"):
                row[key] = int(raw[key])
                require(row[key] >= 0, f"{path}: negative counter")
            require(row["sample_interval"] > 0, f"{path}: invalid interval")
            require(row["timed_calls"] <= row["calls"], f"{path}: too many samples")
            for key in ("estimated_total_ns", "mean_ns"):
                row[key] = float(raw[key]) if raw[key] else None
                require(row[key] is None or math.isfinite(row[key]), f"{path}: nonfinite value")
            require(row["accounting"] in {"reference", "measured", "estimated", "unavailable"},
                    f"{path}: unknown accounting")
            require((row["estimated_total_ns"] is None) == (row["accounting"] == "unavailable"),
                    f"{path}: unavailable accounting mismatch")
            if row["calls"] and row["estimated_total_ns"] is not None:
                require(row["mean_ns"] is not None and close(row["mean_ns"], row["estimated_total_ns"] / row["calls"]),
                        f"{path}: inconsistent mean")
            if not row["calls"]:
                require(row["estimated_total_ns"] == row["sampled_ns"] == 0, f"{path}: nonzero empty category")
            rows[rank, op] = row
    ranks = [str(i) for i in range(processes)]
    require(set(rows) == {(r, op) for r in ranks + ["all"] for op in OPERATIONS},
            f"{path}: missing/extra ranks or operations")
    intervals = {r["sample_interval"] for (_, op), r in rows.items() if op.startswith("MPI_")}
    require(len(intervals) == 1, f"{path}: mixed sampling intervals")
    interval = intervals.pop()
    errors = []
    for rank in ranks + ["all"]:
        reference = rows[rank, "search_total"]
        require(reference["accounting"] == "reference" and reference["sample_interval"] == 1,
                f"{path}: invalid reference")
        expected_calls = processes if rank == "all" else 1
        require(reference["calls"] == reference["timed_calls"] == expected_calls,
                f"{path}: invalid search-window count")
        require(reference["estimated_total_ns"] == reference["sampled_ns"], f"{path}: reference mismatch")
        require(rows[rank, "non_mpi_search"]["sample_interval"] == 1, f"{path}: residual interval")
        if rank != "all":
            for op in OPERATIONS - {"MPI_Iprobe_hit", "MPI_Iprobe_miss"}:
                row = rows[rank, op]
                require(row["timed_calls"] == (row["calls"] + row["sample_interval"] - 1) // row["sample_interval"],
                        f"{path}: invalid sample count {rank}/{op}")
            probes = [rows[rank, op] for op in ("MPI_Iprobe_hit", "MPI_Iprobe_miss")]
            require(sum(r["timed_calls"] for r in probes) == (sum(r["calls"] for r in probes) + interval - 1) // interval,
                    f"{path}: invalid shared probe sample count")
        estimates = [rows[rank, op]["estimated_total_ns"] for op in OPERATIONS - {"search_total"}]
        if all(v is not None for v in estimates):
            error = sum(estimates) - reference["estimated_total_ns"]
            require(close(error, 0, 0.02 if rank != "all" else processes * 0.02),
                    f"{path}: exclusive categories do not reconcile for rank {rank}")
            errors.append(abs(error))
    for op in OPERATIONS:
        aggregate = rows["all", op]
        for key in ("calls", "timed_calls", "sampled_ns"):
            require(aggregate[key] == sum(rows[r, op][key] for r in ranks), f"{path}: aggregate {key} mismatch")
        values = [rows[r, op]["estimated_total_ns"] for r in ranks]
        if any(v is None for v in values):
            require(aggregate["estimated_total_ns"] is None, f"{path}: missing estimate not propagated")
        else:
            require(aggregate["estimated_total_ns"] is not None and close(aggregate["estimated_total_ns"], sum(values), processes * 0.0011),
                    f"{path}: aggregate duration mismatch")
    communication_data(rows, processes)
    return rows, interval, max(errors, default=0)


def load_configurations(directory, definitions=CONFIGS, verify_properties=False):
    configs = []
    for key, folder, processes, nodes in definitions:
        source = directory / folder
        rows, interval, error = read_timing(source / "timing.csv", processes)
        communication = communication_data(rows, processes)
        if communication:
            require(communication["nodes"] == nodes, f"{source}: placement differs from directory label")
        props = json.loads((source / "properties.json").read_text())
        if verify_properties:
            recorded = read_recorded_properties(source, processes)
            require(all(props.get(key) == value for key, value in recorded.items()),
                    f"{source}: properties differ from logs/statistics")
        require(props["coverage"] == 1 and props.get("invalid", 0) == 0, f"{source}: unsuccessful solve")
        for field in ("expanded", "search_time", "total_time"):
            require(math.isfinite(props[field]) and props[field] > 0, f"{source}: invalid {field}")
        require(processes * props["min_expanded"] <= props["expanded"] <= processes * props["max_expanded"],
                f"{source}: expansion bounds")
        require(all(rows["all", op]["estimated_total_ns"] is not None for op in OPERATIONS),
                f"{source}: aggregate estimates unavailable; cannot draw complete breakdown")
        configs.append(dict(id=key, source=source, processes=processes, nodes=nodes,
                            rows=rows, interval=interval, error=error, props=props, communication=communication))
    require(len({c["props"]["optimal_cost"] for c in configs}) == 1, "Different optimal costs")
    return configs


def total(c, op):
    return c["rows"]["all", op]["estimated_total_ns"]


def salbp_configurations(algorithm):
    """Run 921 paths; process and node counts follow recorded topology."""
    prefix = f"salbp-1-{algorithm}"
    return (
        ("96p-1n", f"{prefix}-96-run921-sample100/{algorithm}-run-921", 96, 1),
        ("96p-16n", f"{prefix}-96-16nodes-run921-sample100/96-{algorithm}-run-921", 96, 16),
        ("1536p-16n", f"{prefix}-1536-run921-sample100/{algorithm}-run-921", 1536, 16),
    )


def read_recorded_properties(source, processes):
    """Read log fields for validation against properties and rank statistics."""
    log = (source / "stdout.txt").read_text()
    fields = {"expanded": "Expanded", "min_expanded": "Min expanded",
              "max_expanded": "Max expanded", "search_time": "Search time",
              "total_time": "Total time", "optimal_cost": "optimal cost"}
    props = {}
    for key, label in fields.items():
        matches = re.findall(rf"^{label}: ([0-9.]+)s?$", log, re.MULTILINE)
        require(len(matches) == 1, f"{source}: missing/ambiguous {label}")
        props[key] = float(matches[0]) if key in {"search_time", "total_time", "optimal_cost"} else int(matches[0])
    with (source / "statistics.csv").open(newline="") as stream:
        ranks = list(csv.DictReader(stream))
    require(len(ranks) == processes and {int(r["rank"]) for r in ranks} == set(range(processes)),
            f"{source}: statistics rank mismatch")
    expanded = [int(r["expanded"]) for r in ranks]
    require((sum(expanded), min(expanded), max(expanded)) ==
            tuple(props[k] for k in ("expanded", "min_expanded", "max_expanded")),
            f"{source}: expansion log/statistics mismatch")
    return props


def load_salbp_configurations(directory, algorithm):
    return load_configurations(directory, salbp_configurations(algorithm), verify_properties=True)
