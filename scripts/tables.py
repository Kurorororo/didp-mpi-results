"""Compute the final LaTeX tables directly from the recorded inputs."""
import collections
import math
import re

from .common import (
    DATA, TABLES, SPEC, DOMAINS, read_json, source_path, records,
    usable, positive, cutoff, ratios, geometric_mean as gm, number,
)
from . import mpi

CORES = (1, 96, 768, 1536, 6144, 12288, 24576, 49152)
CONTROL_FIELDS = ('control_messages_tag_1', 'control_messages_tag_2')


def emit(label, rows):
    definition = next(t for t in SPEC['tables'] if t['label'] == label)
    if len(rows) != definition['rows'] or any(len(row) != definition['columns'] for row in rows):
        raise ValueError(f'Unexpected table dimensions: {label}')
    body = definition['header'] + '\n'.join(' & '.join(map(str, row)) + r' \\' for row in rows)
    body += '\n\\bottomrule\n\\end{tabular}\n'
    (TABLES / definition['file'].split('/')[-1]).write_text(body)


def solved_with_counters(row, cores):
    return (row is not None and row.get('coverage') == 1 and usable(row, cores)
            and positive(row, 'search_time', 'expanded'))


def metrics(baseline, target, cores, keys):
    """GM of per-instance ratios; subtract one only after aggregating expansions."""
    co, lb = zip(*(ratios(target[k], cores) for k in keys))
    return [gm(baseline[k]['search_time'] / target[k]['search_time'] for k in keys),
            gm(target[k]['expanded'] / baseline[k]['expanded'] for k in keys) - 1,
            gm(co), gm(lb)]


def cahdbs2():
    data = {p: records('tstpw', 'cabs', p) for p in (96, 768, 1536)}
    keys = sorted(k for k, row in data[96].items()
                  if row.get('coverage') == 1 and cutoff(row) and row['search_time'] <= 300
                  and all(solved_with_counters(rows.get(k), p) and positive(rows[k], 'sent')
                          and all(rows[k].get(f) is not None and math.isfinite(rows[k][f])
                                  and rows[k][f] >= 0 for f in CONTROL_FIELDS)
                          for p, rows in data.items()))
    if not keys:
        raise ValueError('No matched CAHDBS2 instances')
    rows = []
    for p, target in data.items():
        rc = gm(sum(target[k][f] for f in CONTROL_FIELDS) / target[k]['sent'] for k in keys)
        rows.append([f'{p:,}', *map(number, metrics(data[96], target, p, keys)), number(rc)])
    emit('tab:cahdbs2', rows)


def anytime():
    results = {}
    cores = (96, 768, 1536)
    for domain in ('tstpw', 'salpb-1'):
        for algorithm in ('acps', 'apps', 'hac'):
            data = {p: records(domain, algorithm, p) for p in cores}
            candidates = set.intersection(*(set(rows) for rows in data.values()))
            # Each method uses its own 96-core search time for both the cutoff
            # and speedup baseline, with one co-solved cohort across core counts.
            keys = sorted(k for k in candidates if cutoff(data[96][k])
                          and all(solved_with_counters(rows[k], p) for p, rows in data.items()))
            if not keys:
                raise ValueError(f'No matched instances: {domain}/{algorithm}')
            for p in cores:
                results[domain, algorithm, p] = [len(keys) if p == 96 else '',
                                                *map(number, metrics(data[96], data[p], p, keys))]
    rows = []
    for algorithm in ('acps', 'apps', 'hac'):
        for p in cores:
            rows.append([algorithm.upper() if p == 96 else '', f'{p:,}',
                         *results['tstpw', algorithm, p], *results['salpb-1', algorithm, p]])
    emit('tab:tsptw', rows)


def hac_scaling():
    blocks = ((96, 768, 1536), (1536, 6144, 12288), (12288, 24576, 49152))
    for label, domains, selected_blocks in [
        ('tab:tsptw-salbp-1-beyond1536', ('tstpw', 'salpb-1'), blocks[1:]),
        ('tab:m-pdtsp-sualbp-2-beyond1536', ('m-pdtsp', 'sualbp-2'), blocks),
    ]:
        output = []
        for cores in selected_blocks:
            base = cores[0]
            results = {}
            for domain in domains:
                data = {p: records(domain, 'hac', p) for p in cores if source_path(domain, 'hac', p).exists()}
                reference = data[base]
                keys = sorted(k for k, row in reference.items()
                              if row.get('coverage') == 1 and cutoff(row) and row['search_time'] <= 300
                              and all(solved_with_counters(rows.get(k), p) for p, rows in data.items()))
                if not keys:
                    raise ValueError(f'No matched HAC instances: {domain}/{base}')
                for p in cores:
                    results[domain, p] = [len(keys) if p == base else '', *(
                        map(number, metrics(reference, data[p], p, keys)) if p in data else ['--'] * 4)]
            for p in cores:
                output.append([f'{base:,}' if p == base else '', f'{p:,}',
                               *results[domains[0], p], *results[domains[1], p]])
        emit(label, output)


def brfs():
    # Join logs using instance identities; run IDs differ between data generations.
    layers = {}
    for log in (DATA / 'brfs-runs').glob('*/brfs2-*/*/stdout.txt'):
        meta = read_json(log.with_name('static-properties.json'))
        key = (meta['domain'], meta['problem'], int(log.parts[-3].split('-')[-1]))
        if key in layers:
            raise ValueError(f'Duplicate BrFS2 log: {key}')
        layers[key] = len(re.findall(r'^Searched layer:', log.read_text(), re.M))

    def complete(row):
        return not row.get('invalid', 0) and (row.get('coverage') == 1 or row.get('proved_infeasible') == 1)

    cases = [
        ('tstpw', r'\cite{Ohlmann2007}', 'OhlmannThomas',
         ('n150w140.004.txt', 'n150w160.001.txt'), (12288, 24576)),
        ('salpb-1', 'Large', 'large data set_n=100',
         tuple(f'instance_n=100_{i}.alb' for i in (60, 205, 209, 221, 354)), (12288,)),
    ]
    output = []
    for domain, set_label, instance_set, problems, core_counts in cases:
        data = {(a, p): records(domain, a, p) for a in ('brfs2', 'brfs3') for p in core_counts}
        for index, problem in enumerate(problems):
            key = (instance_set, problem)
            shortest = min(rows[key]['total_time'] for rows in data.values() if complete(rows[key]))
            instance = problem.removesuffix('.txt').removeprefix('instance_').removesuffix('.alb')
            for core_index, p in enumerate(core_counts):
                cells = [DOMAINS[domain] if index == core_index == 0 else '',
                         set_label if index == core_index == 0 else '',
                         instance.replace('_', r'\_') if core_index == 0 else '', f'{p:,}']
                for algorithm in ('brfs2', 'brfs3'):
                    row = data[algorithm, p][key]
                    time = row.get('total_time') if complete(row) else None
                    if time is not None and (not math.isfinite(time) or time <= 0):
                        raise ValueError('Invalid completion time')
                    text = f'{time:.0f}' if time is not None else 'OOM'
                    if time == shortest:
                        text = r'\textbf{' + text + '}'
                    cells += [text, *(map(number, ratios(row, p)) if usable(row, p) else ['-', '-'])]
                    if algorithm == 'brfs2':
                        # Modeled synchronization traffic, not measured tag counters.
                        rc = 2*p*(p-1)*layers[(*key, p)] / row['sent'] if time is not None else None
                        cells.append(number(rc) if rc is not None else '-')
                output.append(cells)
    emit('tab:brfs', output)


def communication_rows(configs):
    totals, rates = [], []
    for c in configs:
        op = c['rows']['all', 'MPI_Bsend']
        n = c['props']['expanded']
        messages_in, bytes_in, messages_out, bytes_out = (int(op[k]) for k in mpi.VOLUME_FIELDS)
        if messages_in + messages_out != op['calls']:
            raise ValueError('MPI_Bsend locality counts do not sum to total calls')
        name = f"{c['processes']:,} cores / {c['nodes']} machine{'s' if c['nodes'] != 1 else ''}"
        totals.append([name, number(c['props']['search_time']), f'{n/1e6:,.3f}',
                       f'{messages_in/1e6:,.3f}', f'{messages_out/1e6:,.3f}',
                       f'{bytes_in/1e9:,.3f}', f'{bytes_out/1e9:,.3f}'])
        rates.append([name, *[number(v/n) for v in (messages_in, messages_out, bytes_in, bytes_out)]])
    return totals, rates


def communication():
    totals, rates = communication_rows(mpi.load_configurations(DATA / 'mpi-timing'))
    emit('tab:communication', totals)
    emit('tab:communication-per-expansion', rates)
    for algorithm in ('acps', 'apps'):
        totals, rates = communication_rows(mpi.load_salbp_configurations(DATA / 'mpi-timing', algorithm))
        emit(f'tab:communication-salbp-1-{algorithm}-run921', totals)
        emit(f'tab:communication-per-expansion-salbp-1-{algorithm}-run921', rates)


def speedup():
    output = []
    for domain, label in DOMAINS.items():
        one, many = records(domain, 'hac', 1), records(domain, 'hac', 96)
        if one.keys() != many.keys():
            raise ValueError(f'Different 1/96-core instance sets: {domain}')
        bins, only_96 = [0] * 8, 0
        for key in sorted(one):
            a, b = one[key], many[key]
            if a.get('invalid', 0) or b.get('invalid', 0):
                raise ValueError(f'Invalid speedup record: {key}')
            for row in (a, b):
                if row['coverage'] == 1 and not positive(row, 'total_time'):
                    raise ValueError(f'Invalid solved runtime: {key}')
            if b['coverage'] != 1 or b['total_time'] < 1:
                continue
            if a['coverage'] != 1:
                only_96 += 1
            elif a['total_time'] >= 1:
                ratio = a['total_time'] / b['total_time']
                index = next((i for i, bound in enumerate((1, 16, 32, 48, 64, 80)) if ratio < bound),
                             6 if ratio <= 96 else 7)
                bins[index] += 1
        output.append([label, sum(bins), *bins, only_96])
    emit('tab:hac-1-96', output)


def closures():
    refs = DATA / "solution-ledgers"
    class1 = read_json(refs / "m-pdtsp/class1-solutions.json")
    large = read_json(refs / "m-pdtsp/class1-large-solutions.json")
    class1_closed = sorted((r for r in class1 if (r.get('closed_by') or '').startswith('HAC ')),
                           key=lambda r: (int(r['closed_by'].split()[-1]), r['name']))
    # Keep the manuscript instance ordering; all entries are calculated from the ledger.
    class1_order = SPEC['selections']['closed_m_pdtsp_order']
    rank = {name: i for i, name in enumerate(class1_order)}
    class1_closed.sort(key=lambda r: rank.get(r['name'].removesuffix('.tsp'), len(rank)))
    emit("tab:closed-m-pdtsp", [[r['name'].removesuffix('.tsp'),
         'infeasible' if r.get('proved_infeasible') else f"{r['best_known_solution_cost']:.0f}",
         'HAC', r['closed_by'].split()[-1]] for r in class1_closed])

    # TSPTW's prior open/closed snapshot is incomplete: explicitly reproduce the
    # cohort listed in the submission, without claiming it is the universe of new closures.
    selected = SPEC['selections']['closed_tsptw']
    tsptw_records = []
    for path in sorted((DATA / 'aggregated-properties/tstpw').glob('*-properties.json')):
        tsptw_records.extend(read_json(path).values())
    tsptw_rows, hac_closed = [], {}
    names = {'cabs': 'CAHDBS2', 'acps': 'ACPS', 'apps': 'APPS', 'hac': 'HAC',
             'brfs2': 'BrFS2', 'brfs3': 'BrFS3'}
    for selection in selected:
        instance = selection['instance']
        matches = [r for r in tsptw_records if r['problem'].removesuffix('.txt').removesuffix('.tw') == instance
                   and not r.get('invalid') and r['coverage'] == 1]
        for log in (DATA / 'brfs-runs/tsptw').glob('brfs2-*/*/properties.json'):
            meta = read_json(log.with_name('static-properties.json'))
            r = read_json(log)
            if meta['problem'].removesuffix('.txt') == instance and r.get('proved_infeasible') == 1:
                config = log.with_name('config.yaml').read_text()
                bound = float(re.search(r'^primal_bound: (\S+)', config, re.M).group(1))
                matches.append(dict(algorithm=log.parts[-3], cost=bound, coverage=1,
                                    problem=meta['problem'], domain=meta['domain']))
        if not matches:
            raise ValueError(f"No closure evidence for {instance}")
        min_cores = min(int(r['algorithm'].split('-')[-1]) for r in matches)
        minimum = [r for r in matches if int(r['algorithm'].split('-')[-1]) == min_cores]
        costs = {r['cost'] for r in matches}
        if len(costs) != 1:
            raise ValueError(f"Conflicting optimal costs for {instance}: {costs}")
        algorithms = {r['algorithm'].split('-')[0] for r in minimum}
        methods = ', '.join(label for key, label in names.items() if key in algorithms)
        tsptw_rows.append([selection['instance_set_tex'], instance, f"{costs.pop():.0f}", methods, min_cores])
        for r in matches:
            if r['algorithm'].startswith('hac-'):
                p = int(r['algorithm'].split('-')[-1])
                hac_closed[instance] = min(p, hac_closed.get(instance, p))
    emit('tab:closed-tsptw', tsptw_rows)

    opened = read_json(refs / 'sualbp-2/open_instances.json')
    sualbp = {}
    for p in CORES:
        for r in records('sualbp-2', 'hac', p).values():
            key = r['domain'][-4:] + '/' + r['problem'].lower()
            if key in opened and r['cost'] is not None and r['cost'] == r['bound']:
                sualbp[key] = min(p, sualbp.get(key, p))

    def counts(values):
        c = collections.Counter(values)
        assert set(c) <= set(CORES)
        return [c[p] for p in CORES] + [sum(c.values())]

    def ledger_counts(ledger):
        return counts(int(r['closed_by'].split()[-1]) for r in ledger
                      if (r.get('closed_by') or '').startswith('HAC '))

    emit('tab:closed', [
        ['TSPTW', r'\citet{TSPTWinstances}', *counts(hac_closed.values())],
        ['m-PDTSP', r'\citet{Hernandez-Perez2009}', *ledger_counts(class1)],
        ['', r'\citet{Kuroiwa2023LNBS}', *ledger_counts(large)],
        ['SUALBP-2', r'\citet{Scholl2013}', *counts(sualbp.values())]])
    ledger = read_json(refs / 'sualbp-2/solutions.json')
    rows = []
    for label, field in [('Solution cost', 'solution_cost_obtained_by'),
                         ('Lower bound of the optimal solution cost', 'bound_obtained_by')]:
        rows.append([label, *counts(int(r[field].split()[-1]) for r in ledger
                    if not r['closed'] and r[field].startswith('HAC '))])
    emit('tab:bound', rows)


def build():
    TABLES.mkdir(parents=True, exist_ok=True)
    for generate in (cahdbs2, anytime, hac_scaling, brfs, communication, speedup, closures):
        generate()
