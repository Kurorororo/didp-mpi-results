"""Shared paths, input loading, and numerical definitions."""
from pathlib import Path
import json
import math
import statistics

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / 'data'
PLOTS = ROOT / 'build/plots'
TABLES = ROOT / 'build/tables'
SPEC = json.loads((ROOT / 'config/artifacts.json').read_text())
DOMAINS = {'tstpw': 'TSPTW', 'salpb-1': 'SALBP-1', 'm-pdtsp': 'm-PDTSP', 'sualbp-2': 'SUALBP-2'}


def read_json(path):
    return json.loads(path.read_text())


def source_path(domain, algorithm, cores):
    domain = {'tsptw': 'tstpw', 'salbp-1': 'salpb-1'}.get(domain, domain)
    return DATA / 'aggregated-properties' / domain / f'{algorithm}-{cores}-properties.json'


def records(domain, algorithm, cores):
    """Index records by instance identity, excluding the easy Dumas benchmark."""
    path = source_path(domain, algorithm, cores)
    result = {}
    for row in read_json(path).values():
        if row['domain'] == 'Dumas':
            continue
        key = (row['domain'], row['problem'])
        if key in result:
            raise ValueError(f'Duplicate instance in {path}: {key}')
        result[key] = row
    return result


def usable(row, cores):
    fields = ('sent', 'kept', 'total_assigned', 'max_assigned')
    if any(row.get(k) is None for k in fields):
        return False
    if any(not math.isfinite(float(row[k])) or row[k] < 0 for k in fields):
        raise ValueError('Invalid assignment counter')
    assigned = row['total_assigned']
    if assigned == 0:
        return False
    if row['sent'] + row['kept'] != assigned:
        raise ValueError('total_assigned differs from sent + kept')
    if not assigned / cores <= row['max_assigned'] <= assigned:
        raise ValueError('max_assigned inconsistent with total_assigned')
    return row.get('invalid', 0) != 1


def positive(row, *fields):
    return all(row.get(k) is not None and math.isfinite(row[k]) and row[k] > 0 for k in fields)


def cutoff(row):
    value = row.get('search_time')
    return value is not None and math.isfinite(value) and value >= 10


def ratios(row, cores):
    return row['sent'] / (row['sent'] + row['kept']), cores * row['max_assigned'] / row['total_assigned']


def geometric_mean(values):
    values = list(values)
    if not values or any(not math.isfinite(v) or v < 0 for v in values):
        raise ValueError('Geometric mean requires finite nonnegative values')
    return 0.0 if 0 in values else math.exp(statistics.mean(math.log(v) for v in values))


def number(value):
    text = f'{value:.3f}'
    return '0.000' if text == '-0.000' else text
