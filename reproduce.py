#!/usr/bin/env python3
"""Regenerate the publication plots and tables from the bundled data."""
from pathlib import Path
import argparse
import os
import tempfile
import sys

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parent


def report_outputs(section, directory, format_name):
    from scripts.common import SPEC
    expected = {ROOT / 'build' / entry['file'] for entry in SPEC[section]}
    actual = set((ROOT / 'build' / directory).iterdir())
    if actual != expected or any(not p.is_file() or p.stat().st_size == 0 for p in expected):
        raise ValueError(f'Unexpected or incomplete outputs in build/{directory}/')
    print(f'Wrote {len(expected)} {format_name} to build/{directory}/', flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('target', nargs='?', default='all', choices=('all', 'plots', 'tables'))
    args = parser.parse_args()
    if args.target in ('all', 'plots'):
        # Matplotlib's font cache is temporary, not a build artifact.
        with tempfile.TemporaryDirectory(prefix='didp-matplotlib-') as cache:
            os.environ['MPLCONFIGDIR'] = cache
            os.environ['MPLBACKEND'] = 'Agg'
            os.environ['SOURCE_DATE_EPOCH'] = '1790204400'
            import matplotlib.pyplot as plt
            from scripts import plot_benchmarks, plot_profiles, plot_memory
            from scripts.common import PLOTS
            PLOTS.mkdir(parents=True, exist_ok=True)
            for draw in (plot_benchmarks.build, plot_profiles.failure_modes,
                         plot_profiles.mpi_breakdown, plot_profiles.salbp_mpi_breakdown, plot_memory.build):
                with plt.rc_context():
                    draw()
        report_outputs('figures', 'plots', 'PDFs')
    if args.target in ('all', 'tables'):
        from scripts import tables
        tables.build()
        report_outputs('tables', 'tables', 'LaTeX tables')


if __name__ == '__main__':
    main()
