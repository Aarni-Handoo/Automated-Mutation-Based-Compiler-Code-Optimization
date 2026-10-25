"""Mutation passes, bounded beam search, polynomial verification and timing."""
from dataclasses import replace
import difflib
import itertools
import random
import statistics
import time
from core import Instruction, InputError, apply, execute, tac, python_code, export_tac

OPERATORS = {
 'fold': ('Constant folding', 'Evaluate expressions with two known integer operands.'),
 'zero_add': ('Zero-add removal', 'Adding integer zero preserves the operand.'),
 'one_mul': ('One-mul removal', 'Multiplication by integer one preserves the operand.'),
 'strength': ('Strength reduction', 'For integers, x * 2 equals x + x; no speedup is assumed.'),
 'const_prop': ('Constant propagation', 'Substitute immutable SSA values known to be constants.'),
 'copy_prop': ('Copy propagation', 'Substitute immutable SSA aliases, including output references.'),
 'cse': ('Common subexpression elimination', 'Reuse identical expressions over immutable SSA operands.'),
 'dead': ('Dead-code elimination', 'Remove assignments not needed by the explicit observable outputs.'),
 'zero_mul': ('Zero-mul removal', 'Multiplication by integer zero yields zero.'),
 'sub_zero': ('Subtraction identities', 'Replace x - 0 with x and x - x with zero.'),
 'reorder': ('Independent instruction reorder', 'Swap adjacent instructions only when neither depends on the other.')
}
DEFAULT_OPS = list(OPERATORS)[:-1]


def key(p): return (p.code, p.outputs)


def mutate(p, operator):
    if operator not in OPERATORS: raise InputError('Unknown mutation operator.')
    code, outputs = list(p.code), p.outputs
    if operator in ('const_prop', 'copy_prop'):
        known = {}
        def resolve(x):
            while isinstance(x, str) and x in known: x = known[x]
            return x
        out = []
        for i in code:
            a, b = resolve(i.a), resolve(i.b)
            j = replace(i, a=a, b=b)
            out.append(j)
            if not j.op and ((operator == 'const_prop' and type(a) is int) or (operator == 'copy_prop' and isinstance(a, str))): known[j.dst] = a
        code = out
        outputs = tuple((name, resolve(v)) for name, v in outputs)
    elif operator == 'cse':
        seen, out = {}, []
        for i in code:
            operands = (i.a, i.b)
            if i.op in ('+', '*'): operands = tuple(sorted(operands, key=repr))
            signature = (i.op, operands)
            if i.op and signature in seen: out.append(Instruction(i.dst, seen[signature]))
            else:
                out.append(i)
                if i.op: seen[signature] = i.dst
        code = out
    elif operator == 'dead':
        live = {v for _, v in outputs if isinstance(v, str)}
        out = []
        for i in reversed(code):
            if i.dst in live:
                out.append(i)
                live.discard(i.dst)
                live.update(v for v in (i.a, i.b) if isinstance(v, str))
        code = list(reversed(out))
    elif operator == 'reorder':
        for n in range(len(code)-1):
            a, b = code[n:n+2]
            if a.dst not in (b.a, b.b) and b.dst not in (a.a, a.b):
                code[n:n+2] = [b, a]
                break
    else:
        out = []
        for i in code:
            value = None
            if operator == 'fold' and i.op and type(i.a) is int and type(i.b) is int:
                value = apply(i.a, i.op, i.b)
                if abs(value).bit_length() > 8192: raise InputError('Constant-folding resource limit exceeded.')
            elif operator == 'zero_add' and i.op == '+':
                if i.a == 0: value = i.b
                elif i.b == 0: value = i.a
            elif operator == 'one_mul' and i.op == '*':
                if i.a == 1: value = i.b
                elif i.b == 1: value = i.a
            elif operator == 'zero_mul' and i.op == '*' and (i.a == 0 or i.b == 0): value = 0
            elif operator == 'sub_zero' and i.op == '-':
                if i.b == 0: value = i.a
                elif i.a == i.b: value = 0
            elif operator == 'strength' and i.op == '*':
                if i.a == 2: i = replace(i, a=i.b, op='+')
                elif i.b == 2: i = replace(i, op='+', b=i.a)
            out.append(Instruction(i.dst, value) if value is not None else i)
        code = out
    return replace(p, code=tuple(code), outputs=outputs)


def metrics(p):
    n, a = len(p.code), sum(bool(i.op) for i in p.code)
    t = len({i.dst for i in p.code})
    return {'instructions': n, 'arithmetic': a, 'temporaries': t, 'static_cost': round(n+2*a+1.2*t, 4)}


def cases(inputs, seed, count=40):
    fixed = [dict.fromkeys(inputs, n) for n in (-100, -1, 0, 1, 100)]
    for name in inputs:
        for n in (-1, 1): fixed.append({x: n if x == name else 0 for x in inputs})
    rng = random.Random(seed)
    return fixed + [{name: rng.randint(-1000, 1000) for name in inputs} for _ in range(count)]


def mismatch(original, candidate, samples):
    for inputs in samples:
        expected = execute(original, inputs)
        actual = execute(candidate, inputs)
        if actual != expected: return {'inputs': inputs, 'original': expected, 'candidate': actual}
    return None


class SymbolicLimit(Exception): pass


def polynomials(p):
    """Exact sparse polynomial normal forms; bounded size/work, no external solver.
    Keys are monomials represented as sorted tuples of input variable names.
    """
    env = {x: {(x,): 1} for x in p.inputs}
    work = 0
    def get(v): return ({(): v} if v else {}) if type(v) is int else env[v]
    for i in p.code:
        a = get(i.a)
        if not i.op: result = a.copy()
        elif i.op in ('+', '-'):
            result = a.copy()
            for term, value in get(i.b).items(): result[term] = result.get(term, 0) + (value if i.op == '+' else -value)
        else:
            b = get(i.b)
            work += len(a) * len(b)
            if work > 30000: raise SymbolicLimit()
            result = {}
            for t, x in a.items():
                for u, y in b.items():
                    if len(t)+len(u) > 64: raise SymbolicLimit()
                    term = tuple(sorted(t+u))
                    result[term] = result.get(term, 0) + x*y
        result = {t: x for t, x in result.items() if x}
        if len(result) > 1500 or any(abs(v).bit_length() > 8192 for v in result.values()): raise SymbolicLimit()
        env[i.dst] = result
    return tuple((name, get(v)) for name, v in p.outputs)


def verify(original, candidate, samples, expected_poly=None):
    failure = mismatch(original, candidate, samples)
    if failure: return {'valid': False, 'method': 'output mismatch', 'counterexample': failure}
    try:
        expected_poly = expected_poly if expected_poly is not None else polynomials(original)
        equal = expected_poly == polynomials(candidate)
        return {'valid': equal, 'method': 'exact polynomial identity' if equal else 'polynomial mismatch', 'counterexample': None}
    except SymbolicLimit:
        return {'valid': True, 'method': 'tests only; symbolic resource limit', 'counterexample': None}


def paired_timing(original, selected, samples):
    """Comparable interpreter timings. Alternate order, keep parsing/search outside."""
    samples = samples[:8]
    for p in (original, selected):
        for case in samples: execute(p, case)
    raw = [[], []]
    repeats = 15
    for batch in range(7):
        for idx in ((0, 1) if batch % 2 == 0 else (1, 0)):
            p = (original, selected)[idx]
            start = time.perf_counter_ns()
            for _ in range(repeats):
                for case in samples: execute(p, case)
            raw[idx].append((time.perf_counter_ns()-start)/1000/(repeats*len(samples)))
    summaries = []
    for values in raw:
        summaries.append({'median_us': round(statistics.median(values), 4), 'min_us': round(min(values), 4), 'max_us': round(max(values), 4), 'batches_us': values})
    a, b = summaries
    ratio = a['median_us']/max(b['median_us'], 0.0001)
    overlap = not (a['min_us'] > b['max_us'] or b['min_us'] > a['max_us'])
    return {'original': a, 'selected': b, 'speedup': round(ratio, 3), 'overlapping_ranges': overlap,
            'label': 'TAC interpreter execution; 7 alternating batches, 120 executions per batch',
            'conclusion': 'Timing ranges overlap; no clear speedup.' if overlap else ('Selected interpreter execution is faster in this run.' if ratio > 1 else 'Selected interpreter execution is slower in this run.')}


def baseline(p, enabled, rounds=1):
    current = p
    for _ in range(rounds):
        previous = key(current)
        for op in enabled: current = mutate(current, op)
        if key(current) == previous: break
    return current


def optimize(p, rounds=8, budget=200, beam_width=4, enabled=None, seed=7, measure=True, runtime_weight=0):
    rounds, budget, beam_width = int(rounds), int(budget), int(beam_width)
    if not 1 <= rounds <= 20 or not 1 <= budget <= 800 or not 1 <= beam_width <= 8: raise InputError('Limits: rounds 1–20, budget 1–800, beam width 1–8.')
    enabled = DEFAULT_OPS if enabled is None else enabled
    if not isinstance(enabled, list) or not enabled or len(enabled) > len(OPERATORS) or any(x not in OPERATORS for x in enabled): raise InputError('Select at least one valid operator.')
    enabled = list(dict.fromkeys(enabled))
    runtime_weight = float(runtime_weight)
    if not 0 <= runtime_weight <= 100: raise InputError('Runtime weight must be between 0 and 100.')
    samples = cases(p.inputs, int(seed), 20)
    final_cases = cases(p.inputs, int(seed)+100003, 80)
    try: expected_poly = polynomials(p)
    except SymbolicLimit: expected_poly = None
    # Reject original programs that exceed interpreter resource bounds on validation cases.
    for sample in samples + final_cases: execute(p, sample)
    start = time.perf_counter()
    timing_inputs = samples[:8]
    score_cache = {}
    def score(program):
        k = key(program)
        if k not in score_cache:
            static = metrics(program)['static_cost']
            microseconds = paired_timing(program, program, timing_inputs)['original']['median_us'] if runtime_weight else 0
            score_cache[k] = round(static + runtime_weight * microseconds, 6)
        return score_cache[k]
    first = {'id': 0, 'parent': None, 'round': 0, 'operator': 'Original', 'cost': score(p), 'metrics': metrics(p), 'valid': True, 'code': tac(p), 'changes': '', 'method': 'reference'}
    nodes, programs, frontier = [first], {0: p}, [0]
    seen, best = {key(p)}, 0
    history = [{'evaluations': 0, 'round': 0, 'best_cost': first['cost']}]
    counterexamples, skipped, used_rounds = [], 0, 0
    stop_reason = 'Round limit reached'
    for round_no in range(1, rounds+1):
        used_rounds = round_no
        new = []
        for parent in frontier:
            for op in enabled:
                if len(nodes)-1 >= budget: break
                candidate = mutate(programs[parent], op)
                k = key(candidate)
                if k in seen:
                    skipped += 1
                    continue
                seen.add(k)
                result = verify(p, candidate, [x['inputs'] for x in counterexamples] + samples, expected_poly)
                if result['counterexample']: counterexamples.append(result['counterexample'])
                node_id = len(nodes)
                cost = score(candidate) if result['valid'] else None
                changes = '\n'.join(difflib.unified_diff(tac(programs[parent]).splitlines(), tac(candidate).splitlines(), fromfile='parent', tofile='candidate', lineterm=''))
                node = {'id': node_id, 'parent': parent, 'round': round_no, 'operator': OPERATORS[op][0], 'reason': OPERATORS[op][1], 'cost': cost, 'metrics': metrics(candidate), 'code': tac(candidate), 'changes': changes, **result}
                nodes.append(node)
                if result['valid']:
                    programs[node_id] = candidate
                    new.append(node_id)
                    if cost < nodes[best]['cost']: best = node_id
                history.append({'evaluations': len(nodes)-1, 'round': round_no, 'best_cost': nodes[best]['cost']})
            if len(nodes)-1 >= budget: break
        if len(nodes)-1 >= budget:
            stop_reason = 'Candidate budget reached'
            break
        if not new:
            stop_reason = 'No unseen candidates remain in the retained frontier'
            break
        # Beam may retain equal-cost or temporarily higher-cost alternatives; best-so-far never worsens.
        frontier = sorted(new, key=lambda i: (nodes[i]['cost'], i))[:beam_width]
    search_ms = (time.perf_counter()-start)*1000
    selected = programs[best]
    final = verify(p, selected, final_cases, expected_poly)
    if not final['valid']: raise InputError('Independent final validation failed; no optimized program will be exported.')
    base_results = []
    for title, n in [('Fixed passes (one cycle)', 1), ('Repeated fixed passes', 12)]:
        t = time.perf_counter()
        b = baseline(p, enabled, n)
        verification = verify(p, b, final_cases, expected_poly)
        base_results.append({'name': title, 'metrics': metrics(b), 'valid': verification['valid'], 'method': verification['method'], 'elapsed_ms': round((time.perf_counter()-t)*1000, 3), 'code': tac(b)})
    path, at = [], best
    while at is not None:
        path.append(at)
        at = nodes[at]['parent']
    original_metrics, selected_metrics = metrics(p), metrics(selected)
    reduction = 100*(original_metrics['static_cost']-selected_metrics['static_cost'])/max(original_metrics['static_cost'], 1)
    demo = {name: index+3 for index, name in enumerate(p.inputs)}
    return {'mode': p.mode, 'name': p.name, 'inputs': list(p.inputs), 'outputs': [n for n, _ in p.outputs],
      'original_tac': tac(p), 'optimized_tac': tac(selected), 'optimized_python': python_code(selected), 'download_tac': export_tac(selected),
      'original_metrics': original_metrics, 'optimized_metrics': selected_metrics,
      'nodes': nodes, 'history': history, 'winning_path': list(reversed(path)), 'selected_id': best,
      'validation': {**final, 'search_cases': len(samples), 'independent_cases': len(final_cases), 'counterexamples': counterexamples,
        'scope': 'Exact polynomial identity is over mathematical integers in the supported straight-line +,-,* IR. It does not prove frontend correctness or resource behavior. Input tests use a separate final seed.'},
      'summary': {'candidates': len(nodes)-1, 'valid_candidates': sum(x['valid'] for x in nodes[1:]), 'duplicates_skipped': skipped,
        'validity_rate': round(100*sum(x['valid'] for x in nodes[1:])/max(len(nodes)-1, 1), 2) if len(nodes)>1 else None,
        'rounds': used_rounds, 'search_ms': round(search_ms, 3), 'cost_reduction_percent': round(reduction, 2), 'stop_reason': stop_reason,
        'runtime_weight': runtime_weight, 'score_definition': 'I + 2A + 1.2T + runtime_weight × median interpreter microseconds'},
      'timing': paired_timing(p, selected, final_cases) if measure else None,
      'baselines': base_results, 'example': {'inputs': demo, 'original': execute(p, demo), 'selected': execute(selected, demo)}}
