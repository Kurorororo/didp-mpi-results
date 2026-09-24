# Plot and table source map

Figures and tables are numbered in source order within `main.tex` and
`appendix.tex`. Input paths below are relative to `data/`, and generator paths
are relative to `scripts/`. All generators run through `reproduce.py`.

## Plots

All output files below are in `build/plots/`.

| Document / figure | PDF | Generator | Input / parameters |
|---|---|---|---|
| Main 1 | `cabs-tsptw-optimality.pdf` | `plot_benchmarks.optimality` | `aggregated-properties/tstpw/cabs-{96,768,1536}-properties.json`; 96/768/1536 cores |
| Main 2 | `only-768-tsptw-optimality.pdf` | `plot_benchmarks.optimality` | `aggregated-properties/tstpw/{cabs,acps,apps,hac}-768-properties.json`; cabs/acps/apps/hac at 768 cores |
| Main 3 | `failure-modes.pdf` | `plot_profiles.failure_modes` | Six CSVs in `expansion-statistics/{tsptw-35,salbp-1-1426}` |
| Main 4 | `only-768-salbp-1-optimality.pdf` | `plot_benchmarks.optimality` | `aggregated-properties/salpb-1/{cabs,acps,apps,hac}-768-properties.json`; cabs/acps/apps/hac at 768 cores |
| Main 5 | `hac-tsptw-optimality.pdf` | `plot_benchmarks.optimality` | `aggregated-properties/tstpw/hac-*-properties.json`; 96/768/1536/24576/49152 cores |
| Main 6 | `hac-salbp-1-optimality.pdf` | `plot_benchmarks.optimality` | `aggregated-properties/salpb-1/hac-*-properties.json`; 96/768/1536/12288/24576 cores |
| Main 7 | `hac-m-pdtsp-optimality.pdf` | `plot_benchmarks.optimality` | `aggregated-properties/m-pdtsp/hac-*-properties.json`; 96/768/1536/24576/49152 cores |
| Main 8 | `hac-sualbp-2-optimality.pdf` | `plot_benchmarks.optimality` | `aggregated-properties/sualbp-2/hac-*-properties.json`; 96/768/1536/24576/49152 cores |
| Main 9 | `memory-growth.pdf` | `plot_memory.build` | Four CSVs in `memory-statistics/`; HAC-96 aggregates supply instance identities |
| Appendix 1 | `acps-tsptw-optimality.pdf` | `plot_benchmarks.optimality` | `aggregated-properties/tstpw/acps-{96,768,1536}-properties.json`; 96/768/1536 cores |
| Appendix 2 | `acps-salbp-1-optimality.pdf` | `plot_benchmarks.optimality` | `aggregated-properties/salpb-1/acps-{96,768,1536}-properties.json`; 96/768/1536 cores |
| Appendix 3 | `apps-tsptw-optimality.pdf` | `plot_benchmarks.optimality` | `aggregated-properties/tstpw/apps-{96,768,1536}-properties.json`; 96/768/1536 cores |
| Appendix 4 | `apps-salbp-1-optimality.pdf` | `plot_benchmarks.optimality` | `aggregated-properties/salpb-1/apps-{96,768,1536}-properties.json`; 96/768/1536 cores |
| Appendix 5 | `mpi-breakdown.pdf` | `plot_profiles.mpi_breakdown` | Three timing/property pairs in `mpi-timing/`: 96 cores/1 node, 96/16, 1536/16 |
| Appendix 6 | `hac-96-tsptw-total.pdf`, `hac-96-salbp-1-total.pdf` | `plot_benchmarks.scatter` | `aggregated-properties/<domain>/hac-{1,96}-properties.json` |
| Appendix 7 | `hac-96-m-pdtsp-total.pdf`, `hac-96-sualbp-2-total.pdf` | `plot_benchmarks.scatter` | `aggregated-properties/<domain>/hac-{1,96}-properties.json` |

Optimality curves use total runtime with a 300-second limit, followed by the
remaining relative optimality gap. HAC curves select the HAC-96 cohort with
missing runtime or runtime >=60 seconds, including failures. Other curves use
no runtime cutoff. All benchmark plots exclude Dumas. `cabs` is labeled CAHDBS2
in the 768-core comparison.
Scatter plots include 96-core successes, replace unsolved one-core runs by
300 seconds, clip runtimes above 300, and start both axes at one second.

The heatmap shows ACPS/APPS/HAC at 768 cores on TSPTW `n100w140.001` and
SALBP-1 `n=1000_22`. Expansion counts weight the histograms; panels for each
problem share bin edges and color scales. The memory plot uses rank 0 from
TSPTW run 130, SALBP-1 run 535, m-PDTSP run 90, and SUALBP-2 run 189, with a
1 GB MPI buffer capacity band.

MPI timing uses the interval-100 run-12 snapshots. Rank times are summed and
divided by total expansions. The five groups are non-MPI residual, MPI_Bsend,
MPI_Recv, combined MPI_Iprobe, and other MPI. Sampled time estimates are distinct
from exact message/byte counters; signed per-rank residuals are preserved.

## Tables

All output files below are in `build/tables/`; functions are in `tables.py`.
Headers and instance selections come from `config/artifacts.json`. Numerical
result cells are computed from data.

| Document / table | LaTeX file | Function | Inputs |
|---|---|---|---|
| Main 1 | `cahdbs2.tex` | `cahdbs2` | `aggregated-properties/tstpw/cabs-{96,768,1536}-properties.json` |
| Main 2 | `tsptw.tex` | `anytime` | TSPTW/SALBP-1 acps/apps/hac aggregates at 96/768/1536 cores |
| Main 3 | `tsptw-salbp-1-beyond1536.tex` | `hac_scaling` | TSPTW/SALBP-1 HAC aggregates; blocks (1536,6144,12288) and (12288,24576,49152) |
| Main 4 | `m-pdtsp-sualbp-2-beyond1536.tex` | `hac_scaling` | m-PDTSP/SUALBP-2 HAC aggregates; same blocks plus (96,768,1536) |
| Main 5 | `brfs.tex` | `brfs` | TSPTW BrFS2/3 aggregates at 12288/24576; SALBP-1 at 12288; BrFS2 logs in `brfs-runs/` |
| Appendix 1 | `communication.tex` | `communication` | MPI_Bsend counters, bytes, expansions, and search times in `mpi-timing/` |
| Appendix 2 | `communication-per-expansion.tex` | `communication` | Same counters divided by total expansions |
| Appendix 3 | `hac-1-96.tex` | `speedup` | HAC 1/96 aggregates for all four problem classes |
| Appendix 4 | `closed-tsptw.tex` | `closures` | Selected instance names, TSPTW aggregates, BrFS2 proof logs/configuration |
| Appendix 5 | `closed-m-pdtsp.tex` | `closures` | `solution-ledgers/m-pdtsp/class1-solutions.json`, attributed to HAC |
| Appendix 6 | `closed.tex` | `closures` | TSPTW selected cohort; m-PDTSP class1/class1-large ledgers; SUALBP-2 prior-open list and HAC aggregates |
| Appendix 7 | `bound.tex` | `closures` | `solution-ledgers/sualbp-2/solutions.json`, HAC-attributed bounds on still-open entries |

Metrics use per-instance ratios before taking geometric means (GM):

- Speedup = GM(reference search time / target search time).
- SO = GM(target expansions / reference expansions) − 1.
- CO = GM(sent / (sent + kept)).
- LB = GM(cores × max_assigned / total_assigned).
- CAHDBS2 RC = GM((control_messages_tag_1 + control_messages_tag_2) / sent).
- BrFS2 RC = `2*p*(p-1)*logged_layers/sent` per instance, using modeled
  synchronization traffic and `p` cores.

CAHDBS2 uses 38 co-solved cases, with 10–300 search seconds at 96 cores.
HAC scaling uses reference-solved instances taking 10–300 search seconds, with
positive times/expansions and valid counters at every available configuration
in a block. Missing SALBP-1 49152-core data are shown as dashes.
The ACPS/APPS/HAC comparison selects each algorithm's co-solved instances using
that algorithm's own 96-core search time >=10 seconds. The same instances must
be solved with valid counters at 96, 768, and 1536 cores, and speedups use the
algorithm's own 96-core run. Dumas and separate 30-minute experiments are excluded.

The speedup distribution uses paired successes with both total runtimes >=1
second; eligible successes at 96 cores alone are counted separately. BrFS times
use total runtime. A BrFS proof of no improvement uses its configured primal
bound; logs are joined by instance identity, not run number.

Closure counts use the selected TSPTW cohort and solution-ledger attribution.
SUALBP-2 closure core counts take the minimum over recorded HAC solutions.
Bound-improvement counts attribute each best remaining bound to the HAC
configuration named in the ledger.

## Data organization

`aggregated-properties/` is the single source of benchmark results for all
runtime/gap plots, scatter plots, and numerical result tables, including
CAHDBS2. The original directory spellings `tstpw` and `salpb-1` are retained;
the shared loader maps TSPTW and SALBP-1 plot names to those directories.

The profiling figures additionally need the bundled expansion, memory, and MPI
traces. BrFS tables use recorded logs for layer counts and proofs.
`solution-ledgers/` contains solved-instance lists and best-bound attribution
for closure and improvement tables. Every path used by the generators resolves
inside this project; no archived scripts or external source files are required.
