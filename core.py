"""Restricted integer Python/TAC frontends and immutable SSA intermediate code.
No submitted source is executed with eval/exec. All supported arithmetic is interpreted.
"""
import ast
import keyword
import re
from dataclasses import dataclass, replace

class InputError(ValueError):
    pass

@dataclass(frozen=True)
class Instruction:
    dst: str
    a: object
    op: str = ''
    b: object = None

@dataclass(frozen=True)
class Program:
    code: tuple
    inputs: tuple
    outputs: tuple  # (observable name, SSA value)
    name: str = 'optimized'
    mode: str = 'tac'


def apply(a, op, b):
    if op == '+': return a + b
    if op == '-': return a - b
    if op == '*': return a * b
    raise InputError('Only +, - and * are supported.')


def constant(node):
    if isinstance(node, ast.Constant) and type(node.value) is int:
        if abs(node.value).bit_length() > 128:
            raise InputError('Integer literals must fit within 128 bits.')
        return node.value
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.USub, ast.UAdd)):
        value = constant(node.operand)
        if value is not None: return -value if isinstance(node.op, ast.USub) else value
    return None


def identifier(name):
    return bool(re.fullmatch(r'[A-Za-z_]\w*', name)) and not keyword.iskeyword(name)


def parse(source, mode='python', output_names=None):
    if not isinstance(source, str) or not source.strip(): raise InputError('Enter a program first.')
    if len(source) > 20000: raise InputError('Limit: 20,000 source characters.')
    if mode not in ('python', 'tac'): raise InputError('Choose Python or TAC.')
    try:
        return parse_python(source) if mode == 'python' else parse_tac(source, output_names)
    except (SyntaxError, RecursionError) as error:
        raise InputError(f'Invalid or excessively nested syntax: {error}') from error


class Builder:
    def __init__(self, names):
        self.code, self.env, self.inputs = [], {}, []
        self.prefix = '__m'
        while any(name.startswith(self.prefix) for name in names): self.prefix += '_'
    def emit(self, a, op='', b=None):
        if len(self.code) >= 150: raise InputError('Limit: 150 intermediate instructions.')
        dst = self.prefix + str(len(self.code))
        self.code.append(Instruction(dst, a, op, b))
        return dst
    def input(self, name):
        if name not in self.inputs: self.inputs.append(name)
        self.env[name] = name
    def expr(self, node, implicit=False):
        value = constant(node)
        if value is not None: return value
        if isinstance(node, ast.Name):
            if node.id not in self.env:
                if not implicit: raise InputError(f'Variable {node.id!r} is used before assignment.')
                self.input(node.id)
            return self.env[node.id]
        if isinstance(node, ast.BinOp) and isinstance(node.op, (ast.Add, ast.Sub, ast.Mult)):
            left, right = self.expr(node.left, implicit), self.expr(node.right, implicit)
            op = {ast.Add: '+', ast.Sub: '-', ast.Mult: '*'}[type(node.op)]
            return self.emit(left, op, right)
        if isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.USub, ast.UAdd)):
            operand = self.expr(node.operand, implicit)
            return self.emit(0, '-', operand) if isinstance(node.op, ast.USub) else operand
        raise InputError('Supported expressions: integer constants, names, parentheses, +, -, and *. No calls or other operators.')


def check_annotation(node):
    if node is not None and not (isinstance(node, ast.Name) and node.id == 'int'):
        raise InputError('Only optional int annotations are supported.')


def parse_python(source):
    tree = ast.parse(source)
    if len(tree.body) != 1 or not isinstance(tree.body[0], ast.FunctionDef):
        raise InputError('Python mode expects exactly one function definition; no imports or top-level execution.')
    fn = tree.body[0]
    args = fn.args
    if fn.decorator_list or args.posonlyargs or args.kwonlyargs or args.vararg or args.kwarg or args.defaults:
        raise InputError('Use ordinary positional parameters without defaults, decorators, or variadic arguments.')
    check_annotation(fn.returns)
    for arg in args.args: check_annotation(arg.annotation)
    names = {n.id for n in ast.walk(fn) if isinstance(n, ast.Name)} | {a.arg for a in args.args}
    b = Builder(names)
    for arg in args.args: b.input(arg.arg)
    if len(b.inputs) > 12: raise InputError('Limit: 12 input parameters.')
    body = fn.body
    if body and isinstance(body[0], ast.Expr) and isinstance(body[0].value, ast.Constant) and isinstance(body[0].value.value, str): body = body[1:]
    if not body or not isinstance(body[-1], ast.Return) or body[-1].value is None:
        raise InputError('End the function with one integer return expression.')
    for stmt in body[:-1]:
        if isinstance(stmt, ast.Assign) and len(stmt.targets) == 1 and isinstance(stmt.targets[0], ast.Name):
            target, expr = stmt.targets[0].id, stmt.value
        elif isinstance(stmt, ast.AnnAssign) and isinstance(stmt.target, ast.Name) and stmt.value is not None:
            check_annotation(stmt.annotation)
            target, expr = stmt.target.id, stmt.value
        else:
            raise InputError('Only local assignments followed by a final return are supported. Loops, branches and calls are outside this version.')
        b.env[target] = b.emit(b.expr(expr))
    result = b.expr(body[-1].value)
    return Program(tuple(b.code), tuple(b.inputs), (('return', result),), fn.name, 'python')


def parse_tac(source, output_names):
    names = set(re.findall(r'[A-Za-z_]\w*', source))
    b = Builder(names)
    assigned = []
    for index, raw in enumerate(source.splitlines(), 1):
        line = raw.split('#')[0].split('//')[0].strip().rstrip(';').strip()
        if not line: continue
        tree = ast.parse(line)
        if len(tree.body) != 1 or not isinstance(tree.body[0], ast.Assign):
            raise InputError(f'Line {index}: expected an assignment, such as result = a + b.')
        stmt = tree.body[0]
        if len(stmt.targets) != 1 or not isinstance(stmt.targets[0], ast.Name): raise InputError('TAC destinations must be single variable names.')
        target = stmt.targets[0].id
        expr = stmt.value
        atom = lambda n: isinstance(n, ast.Name) or constant(n) is not None
        if not atom(expr) and not (isinstance(expr, ast.BinOp) and isinstance(expr.op, (ast.Add, ast.Sub, ast.Mult)) and atom(expr.left) and atom(expr.right)):
            raise InputError(f'Line {index}: TAC allows at most one operation. Use Python mode for nested expressions.')
        # Avoid an unnecessary alias instruction for TAC binary expressions.
        value = b.expr(expr, True)
        b.env[target] = value if isinstance(expr, ast.BinOp) else b.emit(value)
        if target not in assigned: assigned.append(target)
    if not assigned: raise InputError('No TAC instructions found.')
    if isinstance(output_names, str): output_names = [x.strip() for x in output_names.split(',') if x.strip()]
    outputs = output_names or [name for name in assigned if not re.fullmatch(r't\d+', name)]
    if not outputs: raise InputError('Specify output variables, or assign a non-temporary output such as result.')
    if len(set(outputs)) != len(outputs) or any(name not in assigned for name in outputs): raise InputError('Outputs must be unique variables assigned in this program.')
    if len(b.inputs) > 12: raise InputError('Limit: 12 inputs.')
    return Program(tuple(b.code), tuple(b.inputs), tuple((name, b.env[name]) for name in outputs), 'optimized', 'tac')


def execute(program, inputs):
    if any(name not in inputs or type(inputs[name]) is not int for name in program.inputs):
        raise InputError('Supply ordinary built-in integer values for every input.')
    env = {name: inputs[name] for name in program.inputs}
    def get(x): return x if type(x) is int else env[x]
    for i in program.code:
        value = apply(get(i.a), i.op, get(i.b)) if i.op else get(i.a)
        if abs(value).bit_length() > 8192: raise InputError('Execution exceeded the 8192-bit integer resource limit.')
        env[i.dst] = value
    return {name: get(value) for name, value in program.outputs}


def expression(i):
    return f'{i.a} {i.op} {i.b}' if i.op else str(i.a)


def tac(program):
    lines = [f'{i.dst} = {expression(i)}' for i in program.code]
    lines += [f'output {name} = {value}' for name, value in program.outputs]
    return '\n'.join(lines)


def python_code(program):
    lines = [f'def {program.name}({", ".join(program.inputs)}):']
    body = list(program.code)
    returned = str(program.outputs[0][1])
    if program.mode == 'python' and body and body[-1].dst == program.outputs[0][1]:
        returned = expression(body.pop())
    lines += [f'    {i.dst} = {expression(i)}' for i in body]
    if program.mode == 'python': lines.append(f'    return {returned}')
    else: lines.append('    return {' + ', '.join(f'{name!r}: {value}' for name, value in program.outputs) + '}')
    return '\n'.join(lines) + '\n'


def export_tac(program):
    # Snapshot every output before writing original names: outputs may refer to inputs.
    names = set(program.inputs) | {i.dst for i in program.code} | {n for n, _ in program.outputs}
    prefix = '__out'
    while any(n.startswith(prefix) for n in names): prefix += '_'
    lines = [f'{i.dst} = {expression(i)}' for i in program.code]
    lines += [f'{prefix}{k} = {v}' for k, (_, v) in enumerate(program.outputs)]
    lines += [f'{n} = {prefix}{k}' for k, (n, _) in enumerate(program.outputs)]
    return '\n'.join(lines) + '\n'
