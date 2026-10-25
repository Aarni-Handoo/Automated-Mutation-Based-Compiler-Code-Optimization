"""Reproducible corpus and CLI exports; synthetic evidence, not real-world claims."""
import argparse
import csv
import json
from pathlib import Path
import random
from core import parse
from engine import optimize


def generate(seed):
    r = random.Random(seed)
    lines = ['t1 = a + 0', 't2 = b * 1', f't3 = {r.randint(-9, 9)} + {r.randint(-9, 9)}']
    available = ['a', 'b', 't1', 't2', 't3']
    for n in range(4, r.randint(8, 15)):
        left = r.choice(available)
        right = r.choice(available + ['0', '1', '2', '-3'])
        lines.append(f't{n} = {left} {r.choice(["+", "-", "*"])} {right}')
        available.append(f't{n}')
    # Include reassignment and repeated expressions to exercise safe SSA lowering.
    if seed % 3 == 0: lines += ['t90 = a + b', 'a = 7', 't91 = a + b', 'result = t90 + t91']
    elif seed % 3 == 1: lines += [f'result = {available[-1]} + t3']
    else: lines += ['t90 = a', 'a = b', 'result = t90 + a']
    return '\n'.join(lines)


def run_benchmark(count=200, progress=None):
    if not 200 <= count <= 500: raise ValueError('Choose 200–500 programs.')
    rows = []
    for index in range(count):
        source = generate(index+101)
        result = optimize(parse(source, 'tac', ['result']), budget=100, rounds=8, measure=False, seed=index+7)
        row = {'program': index+1, 'source': source, 'original_cost': result['original_metrics']['static_cost'],
               'selected_cost': result['optimized_metrics']['static_cost'], 'fixed_cost': result['baselines'][0]['metrics']['static_cost'],
               'repeated_cost': result['baselines'][1]['metrics']['static_cost'], **result['summary'],
               'verification': result['validation']['method'], 'valid': result['validation']['valid']}
        rows.append(row)
        if progress: progress(index+1, count)
    summary = {'programs': count, 'passed_programs': sum(r['valid'] for r in rows),
               'exact_identity_programs': sum(r['verification'] == 'exact polynomial identity' for r in rows),
               'average_static_reduction_percent': round(sum(r['cost_reduction_percent'] for r in rows)/count, 3),
               'average_search_ms': round(sum(r['search_ms'] for r in rows)/count, 3),
               'average_depth': round(sum(r['rounds'] for r in rows)/count, 3),
               'average_validity_percent': round(sum(r['validity_rate'] or 0 for r in rows)/count, 3),
               'search_beats_repeated': sum(r['selected_cost'] < r['repeated_cost'] for r in rows),
               'search_ties_repeated': sum(r['selected_cost'] == r['repeated_cost'] for r in rows),
               'search_loses_repeated': sum(r['selected_cost'] > r['repeated_cost'] for r in rows),
               'note': 'Synthetic straight-line integer TAC corpus. Static cost is not runtime speedup. Baselines are quality references, not equal-work comparisons.'}
    return {'summary': summary, 'rows': rows}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--programs', type=int, default=200)
    parser.add_argument('--out', default='results')
    args = parser.parse_args()
    result = run_benchmark(args.programs)
    folder = Path(args.out)
    folder.mkdir(parents=True, exist_ok=True)
    (folder/'benchmark.json').write_text(json.dumps(result, indent=2), encoding='utf-8')
    with (folder/'benchmark.csv').open('w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=list(result['rows'][0]))
        writer.writeheader()
        writer.writerows(result['rows'])
    print(json.dumps(result['summary'], indent=2))
