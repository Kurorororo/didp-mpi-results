# Reproducing plots and tables

This self-contained project regenerates **20 plot PDFs and 16 LaTeX tables**
from the bundled experiment results.

## Run

Use Python 3.12. From this directory:

```sh
python3 -m venv .venv
. .venv/bin/activate
python -m pip install -r requirements.txt
python reproduce.py
```

The build runs offline after dependencies are installed. It writes only
the final artifacts:

```text
build/
  plots/     20 PDFs
  tables/    16 .tex files
```

To regenerate just one group:

```sh
python reproduce.py plots
python reproduce.py tables
```

Tables need only the Python standard library. `make`, `make plots`, and
`make tables` are optional shortcuts; set `PYTHON` to choose the interpreter.
To count SALBP-1 superlinear runs and how many also have negative search
overhead or an initial dual bound equal to the optimum, run
`python3 scripts/analyze_salbp1_superlinear.py`. It prints Markdown
tables for all paired optimal solves and the paper's >=10-second cohort,
using the bundled ACPS/APPS results and the Python standard library.

To reproduce the SALBP-1 initial dual-bound match counts, run
`python3 scripts/analyze_salbp1_initial_bounds.py`. It reads initial bounds from
HAC-1 `dual_bound_progress` and prints per-configuration, distinct-union,
paired, and paper-cohort counts. No additional dependencies are needed.
The first history entry must record zero expanded states; instances are joined
by `(domain, problem)`.

You can delete `build/` and regenerate it with the same command. Paths are
relative to the project, so the entry point also works from another directory.

The `.tex` files contain `tabular` environments, ready to include in a document
using the original booktabs/natbib conventions. Building them does not require
LaTeX. The project reanalyzes recorded runs; it does not compile the manuscript
or rerun cluster experiments.

## Project layout

| File or directory | Purpose |
|---|---|
| `reproduce.py` | Single build entry point |
| `scripts/plot_benchmarks.py` | Optimality curves and runtime scatter plots |
| `scripts/plot_profiles.py` | Expansion heatmaps and MPI timing plot |
| `scripts/plot_memory.py` | Memory plot |
| `scripts/tables.py` | All table calculations and LaTeX output |
| `scripts/common.py` | Shared paths, input loading, and numerical definitions |
| `scripts/mpi.py` | Shared MPI timing/counter loading and validation |
| `data/` | Required recorded results, traces, logs, and solution ledgers |
| `config/artifacts.json` | Output names, table headers, and selected instance names |
| [SOURCES.md](SOURCES.md) | Plot/table mapping, input datasets, and metric definitions |

All required data are ordinary files inside this project:

| Data directory | Used for |
|---|---|
| `data/aggregated-properties/` | All benchmark plots (including CAHDBS2), result tables, and memory instance labels |
| `data/expansion-statistics/` | Expansion heatmaps |
| `data/memory-statistics/` | Memory plot |
| `data/mpi-timing/` | MPI timing plot and communication tables |
| `data/brfs-runs/` | BrFS layer counts and proof evidence |
| `data/solution-ledgers/` | Solved-instance and bound-improvement tables |

`aggregated-properties/` is the single source of benchmark results for plots
and tables. The other data folders contain the traces, logs, and solution
ledgers needed for the profiling figures and remaining tables.

Copy this directory anywhere and run the same command. No manuscript, original
experiment directory, symlink, or external data download is needed. Command
strings in raw experiment records are metadata and are never executed.

The original 18-plot build was tested from a relocated copy with access to the
original experiment tree blocked. The extended 20-plot build was verified locally.
All 20 PDFs and 16 tables are generated
using only bundled inputs. Rendering versions can affect PDF bytes on other
environments.

The SALBP-1 run 921 MPI breakdowns are saved as
`build/plots/mpi-breakdown-salbp-1-{acps,apps}-run921.pdf`, using the same
categories and normalization as HAC/TSPTW run 12, with a shared vertical scale.
The configurations are 96 cores/1 machine, 96 cores/16 machines, and
1,536 cores/16 machines, verified against the recorded timing topology.
Updated `properties.json` files supply the metrics and are checked against
matching solver logs and per-rank statistics.

Each algorithm also has two HAC-style LaTeX tables in `build/tables/`:
`communication-salbp-1-{acps,apps}-run921.tex` reports search time, expansions,
and intra/inter-machine MPI_Bsend message and payload totals;
`communication-per-expansion-salbp-1-{acps,apps}-run921.tex` reports messages
and payload bytes per expansion. Regenerate everything with `python reproduce.py`.
