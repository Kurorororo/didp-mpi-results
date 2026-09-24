"""The eleven optimality curves and four 1-to-96-core scatter plots."""
import matplotlib.pyplot as plt

from .common import PLOTS, records


def optimality(domain, algorithms, cores, labels, *, cutoff=0, hide_cores=False,
               colors=None, legend='lower right'):
    data = {f'{a}-{p}': records(domain, a, p) for a in algorithms for p in cores}
    names = list(data)
    cohort = {key for key, row in data[names[0]].items()
              if row['total_time'] is None or row['total_time'] >= cutoff}
    times, gaps = {a: [] for a in names}, {a: [] for a in names}
    for a, rows in data.items():
        for key, row in rows.items():
            if key not in cohort:
                continue
            if row['coverage'] == 1:
                times[a].append(min(row['total_time'], 300))
            elif row['bound'] is None or row['cost'] is None or row['cost'] == 0:
                gaps[a].append(1.0)
            else:
                gaps[a].append((row['cost'] - row['bound']) / row['cost'])

    fig, ax = plt.subplots(figsize=(6.5, 2), dpi=900)
    colors = colors or [f'C{i}' for i in range(len(names))]
    for i, (algorithm, label) in enumerate(zip(algorithms, labels)):
        for j, p in enumerate(cores):
            a = f'{algorithm}-{p}'
            x = sorted(times[a]) + sorted(g * 150 + 300 for g in gaps[a])
            if not x:
                raise ValueError(f'Empty optimality series: {domain}/{a}')
            y = [k / len(x) for k in range(len(x))]
            # Include the endpoint of the cumulative curve.
            text = label if hide_cores else f'{label} {p: >5} cores'
            ax.plot(x + [450], y + [1.0], label=text, linewidth=0.8, color=colors[i*len(cores)+j])
    ax.vlines(300, -0.01, 1.05, color='lightgray', linestyles='dashed', linewidth=1.5)
    handles, legend_labels = ax.get_legend_handles_labels()
    ax.legend(handles[::-1], legend_labels[::-1], loc=legend, fontsize=9)
    times = [0, 50, 100, 150, 200, 250, 300]
    gaps = [0.2, 0.4, 0.6, 0.8, 1.0]
    ax.set_xlim(-0.01, 457.5)
    ax.set_ylim(0, 1.05)
    ax.set_xticks(times + [g*150+300 for g in gaps], labels=[str(x) for x in times+gaps], fontsize=9)
    ax.set_yticks([0, 0.2, 0.4, 0.6, 0.8, 1])
    ax.tick_params(axis='y', labelsize=9)
    ax.set_xlabel('                          Time to solve optimally (s) | Optimality gap', fontsize=9)
    ax.set_ylabel('Ratio of instances', fontsize=9)
    fig.tight_layout()
    stem = 'only-768' if hide_cores else algorithms[0]
    fig.savefig(PLOTS / f'{stem}-{domain}-optimality.pdf')
    plt.close(fig)


def scatter(domain):
    baseline = records(domain, 'hac', 1)
    proposed = records(domain, 'hac', 96)
    x_by_key = {(r['domain'], r['problem']): min(r['total_time'], 300) if r['coverage'] == 1 else 300
                for r in baseline.values()}
    solved = [r for r in proposed.values() if r['coverage'] == 1]
    x = [x_by_key[r['domain'], r['problem']] for r in solved]
    y = [min(r['total_time'], 300) for r in solved]
    fig, ax = plt.subplots(figsize=(2.2, 2.2), dpi=900)
    ax.set_xscale('log')
    ax.set_yscale('log')
    ax.set_xlabel('Time (s) with 1 core', fontsize=9)
    ax.set_ylabel('Time (s) with 96 cores', fontsize=9)
    ax.set_xticks([1, 10, 100, 300], labels=['1', '10', '100', r'$\geq300$'], fontsize=9)
    ax.set_yticks([1, 10, 100, 300], labels=['1', '10', '100', '300'], fontsize=9)
    ax.set_xlim(1, 360)
    ax.set_ylim(1, 360)
    ax.scatter(x, y, s=0.3, marker='+')
    for speed in (1, 16, 32, 48, 64, 96):
        label = '1x' if speed == 1 else f'1/{speed}x'
        ax.plot([speed, 360], [1, 360/speed], linestyle=':', label=label, linewidth=0.8)
    ax.set_box_aspect(1)
    fig.subplots_adjust(left=0.55/2.2, right=0.93, bottom=0.3/2.2, top=0.99)
    ax.legend(loc='upper left', fontsize=9)
    fig.savefig(PLOTS / f'hac-96-{domain}-total.pdf')
    plt.close(fig)


def build():
    for domain in ('tsptw', 'salbp-1'):
        for algorithm in ('cabs', 'acps', 'apps'):
            if algorithm == 'cabs' and domain != 'tsptw':
                continue
            optimality(domain, [algorithm], [96, 768, 1536], [''])
        optimality(domain, ['cabs', 'acps', 'apps', 'hac'], [768],
                   ['CAHDBS2', 'ACPS', 'APPS', 'HAC'], hide_cores=True)
    for domain in ('tsptw', 'salbp-1', 'm-pdtsp', 'sualbp-2'):
        cores = [96, 768, 1536, 12288, 24576] if domain == 'salbp-1' else [96, 768, 1536, 24576, 49152]
        colors = ['C0', 'C1', 'C2', 'C5', 'C3'] if domain == 'salbp-1' else None
        legend = 'upper left' if domain == 'm-pdtsp' else 'lower right'
        optimality(domain, ['hac'], cores, [''], cutoff=60, colors=colors, legend=legend)
        scatter(domain)
