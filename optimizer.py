"""Stage 1: a small mutation search over straight-line integer TAC."""
from dataclasses import dataclass, replace
from itertools import product
import random
import re

NAME = r'[A-Za-z_]\w*'
VALUE = rf'(?:{NAME}|-?\d+)'
LINE = re.compile(rf'({NAME})\s*=\s*({VALUE})(?:\s*([+*-])\s*({VALUE}))?')


@dataclass
class Instruction:
    target: str
    left: str
    op: str = ''
    right: str = ''

    def __str__(self):
        expression = f'{self.left} {self.op} {self.right}' if self.op else self.left
        return f'{self.target} = {expression}'


def number(value):
    return re.fullmatch(r'-?\d+', value) is not None


def temporary(name):
    return re.fullmatch(r't\d+', name) is not None


def parse(source):
    code = []
    for line_number, raw in enumerate(source.splitlines(), 1):
        line = raw.split('#', 1)[0].split('//', 1)[0].strip().rstrip(';').strip()
        if not line:
            continue
        match = LINE.fullmatch(line)
        if not match:
            raise ValueError(f'Line {line_number}: expected x = a or x = a + b (also - and *).')
        target, left, op, right = match.groups()
        code.append(Instruction(target, left, op or '', right or ''))
    if not code:
        raise ValueError('The program is empty.')
    return code


def input_names(code):
    assigned, inputs = set(), set()
    for instruction in code:
        for operand in (instruction.left, instruction.right):
            if operand and not number(operand) and operand not in assigned:
                inputs.add(operand)
        assigned.add(instruction.target)
    return sorted(inputs)


def output_names(code):
    # t1, t2, ... are reserved temporaries; names such as total are outputs.
    return sorted({i.target for i in code if not temporary(i.target)})


def calculate(left, op, right):
    if op == '+':
        return left + right
    if op == '-':
        return left - right
    if op == '*':
        return left * right
    raise ValueError(f'Unsupported operator: {op}')


def execute(code, inputs, outputs):
    values = dict(inputs)
    def value(token):
        if number(token):
            return int(token)
        if token not in values:
            raise ValueError(f'Missing input: {token}')
        return values[token]
    for instruction in code:
        result = value(instruction.left)
        if instruction.op:
            result = calculate(result, instruction.op, value(instruction.right))
        values[instruction.target] = result
    return {name: values[name] for name in outputs}


OPERATORS = ('Constant folding', 'Zero-add removal', 'One-mul removal', 'Strength reduction')


def mutate(code, operator):
    """Apply one operator to every matching instruction in a copied program."""
    if operator not in OPERATORS:
        raise ValueError('Unknown mutation.')
    result = [replace(i) for i in code]
    for i in result:
        replacement = None
        if operator == 'Constant folding' and i.op and number(i.left) and number(i.right):
            replacement = str(calculate(int(i.left), i.op, int(i.right)))
        elif operator == 'Zero-add removal' and i.op == '+':
            if number(i.right) and int(i.right) == 0:
                replacement = i.left
            elif number(i.left) and int(i.left) == 0:
                replacement = i.right
        elif operator == 'One-mul removal' and i.op == '*':
            if number(i.right) and int(i.right) == 1:
                replacement = i.left
            elif number(i.left) and int(i.left) == 1:
                replacement = i.right
        elif operator == 'Strength reduction' and i.op == '*':
            if number(i.right) and int(i.right) == 2:
                i.op, i.right = '+', i.left
            elif number(i.left) and int(i.left) == 2:
                i.op, i.left = '+', i.right
        if replacement is not None:
            i.left, i.op, i.right = replacement, '', ''
    return result


def metrics(code):
    instructions = len(code)
    arithmetic = sum(bool(i.op) for i in code)
    temporaries = len({i.target for i in code if temporary(i.target)})
    # Execution-time measurement is planned for the next stage.
    cost = instructions + 2 * arithmetic + 1.2 * temporaries
    return {'instructions': instructions, 'arithmetic': arithmetic,
            'temporaries': temporaries, 'cost': round(cost, 2)}


def make_cases(names, seed=7):
    cases = [dict.fromkeys(names, value) for value in (-100, -1, 0, 1, 100)]
    rng = random.Random(seed)
    cases += [{name: rng.randint(-100, 100) for name in names} for _ in range(20)]
    return cases


def equivalent(original, candidate, cases, outputs):
    return all(execute(original, case, outputs) == execute(candidate, case, outputs)
               for case in cases)


def optimize(source):
    original = parse(source)
    outputs = output_names(original)
    if not outputs:
        raise ValueError('Add a named output, for example result = t4. t1, t2, ... are temporary.')
    cases = make_cases(input_names(original))
    best = original
    best_cost = metrics(original)['cost']
    rows = []
    seen = {tuple(map(str, original))}
    # One search round: singles and ordered pairs. Iterative search is pending.
    sequences = [(name,) for name in OPERATORS] + list(product(OPERATORS, repeat=2))
    for sequence in sequences:
        candidate = original
        for name in sequence:
            candidate = mutate(candidate, name)
        key = tuple(map(str, candidate))
        if key in seen:
            continue
        seen.add(key)
        passed = equivalent(original, candidate, cases, outputs)
        cost = metrics(candidate)['cost']
        candidate_id = len(rows) + 1
        rows.append({'id': candidate_id, 'mutations': ' + '.join(sequence),
                     'passed': passed, 'cost': cost, 'code': candidate})
        if passed and cost < best_cost:
            best, best_cost = candidate, cost
    return {'original': original, 'best': best, 'candidates': rows,
            'outputs': outputs, 'inputs': input_names(original), 'test_count': len(cases)}
