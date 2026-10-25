import unittest
from dataclasses import replace
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from core import parse,execute,python_code,export_tac,InputError
from engine import OPERATORS,DEFAULT_OPS,mutate,optimize,cases,verify,polynomials,SymbolicLimit
from benchmark import generate

class FrontendTests(unittest.TestCase):
    def test_nested_unary(self):
        p=parse('def f(a: int,b: int) -> int:\n    x = -(a + 2) * (b - 3)\n    return x + a')
        self.assertEqual(execute(p,{'a':4,'b':6}),{'return':-14})
    def test_reassignment(self):
        p=parse('def f(a,b):\n    old = a\n    a = b\n    return old - a')
        self.assertEqual(execute(p,{'a':9,'b':2}),{'return':7})
    def test_outputs(self):
        p=parse('total = a + 1\nt1 = total * 2\nresult = t1','tac')
        self.assertEqual([n for n,_ in p.outputs],['total','result'])
        self.assertEqual(execute(parse('t1 = a + 1','tac',['t1']),{'a':2}),{'t1':3})
    def test_read_before_write(self):
        self.assertEqual(execute(parse('x = x + 1\nresult = x','tac'),{'x':3}),{'x':4,'result':4})
    def test_unsupported(self):
        snippets=['import os','def f(a):\n    return print(a)','def f(a):\n    return a / 2','def f(a):\n    return True','def f(a):\n    return 1.5','def f(a):\n    if a:\n        return 1\n    return 2','def f(a=1):\n    return a','def f(a):\n    return missing','@other\ndef f(a):\n    return a']
        for s in snippets:
            with self.subTest(s=s),self.assertRaises(InputError):parse(s)
        for s in ['x = a + b * c','print(x)','t1 = a + 0']:
            with self.assertRaises(InputError):parse(s,'tac')
    def test_input_type_contract(self):
        p=parse('def f(a):\n    return a + 1')
        for value in (True,1.0,'2'):
            with self.assertRaises(InputError):execute(p,{'a':value})
    def test_fresh_names(self):
        p=parse('def f(__m0):\n    x = __m0 + 1\n    return x')
        self.assertEqual(execute(p,{'__m0':3}),{'return':4})
    def test_tac_roundtrip_alias_outputs(self):
        p=parse('saved = x\nx = y\ny = saved','tac',['x','y'])
        for op in DEFAULT_OPS:p=mutate(p,op)
        q=parse(export_tac(p),'tac',['x','y'])
        self.assertEqual(execute(p,{'x':3,'y':7}),execute(q,{'x':3,'y':7}))
    def test_emitted_python(self):
        p=parse('def f(a,b):\n    x = a * 2\n    return x - b')
        namespace={}
        # Only trusted fixed test fixtures and compiler-generated code execute here.
        exec(compile(python_code(p),'<generated-test>','exec'),namespace)
        self.assertEqual(namespace['f'](3,4),execute(p,{'a':3,'b':4})['return'])
    def test_python_frontend_against_python(self):
        for n in range(12):
            s=f'def f(a,b):\n    saved = a\n    a = b + {n}\n    x = (saved - a) * (b + 2)\n    return x + saved'
            p=parse(s);ns={}
            exec(compile(s,'<trusted-generated-test>','exec'),ns)
            for c in cases(p.inputs,n,5):self.assertEqual(execute(p,c)['return'],ns['f'](**c))

class MutationTests(unittest.TestCase):
    def test_reassignment_corpus_all_operators(self):
        corpus=['a = b\nb = 5\nresult = a + b','t1 = a + b\na = 7\nt2 = a + b\nresult = t1 + t2','t1 = a + b\nt1 = 9\nt2 = a + b\nresult = t1 - t2','x = a * 0\ny = b - b\nresult = x + y']
        for s in corpus:
            p=parse(s,'tac',['result'])
            for op in OPERATORS:self.assertTrue(verify(p,mutate(p,op),cases(p.inputs,93))['valid'],op)
    def test_each_operator_changes_matching_code(self):
        fixtures={'fold':'result = 2 + 3','zero_add':'result = x + 0','one_mul':'result = x * 1','strength':'result = x * 2','const_prop':'a = 2\nresult = a + 1','copy_prop':'a = x\nresult = a + 1','cse':'t1 = a + b\nt2 = a + b\nresult = t1 + t2','dead':'unused = 2\nresult = x','zero_mul':'result = x * 0','sub_zero':'result = x - x','reorder':'a = 2\nb = 3\nresult = a + b'}
        for op,s in fixtures.items():
            p=parse(s,'tac',['result']);self.assertNotEqual(p,mutate(p,op),op)
    def test_exact_check_catches_missed_test(self):
        p=parse('result = a + b','tac');q=replace(p,code=(replace(p.code[0],b='a'),))
        check=verify(p,q,[{'a':1,'b':1}]);self.assertFalse(check['valid']);self.assertEqual(check['method'],'polynomial mismatch')
    def test_counterexample(self):
        p=parse('result = a + b','tac');q=replace(p,code=(replace(p.code[0],b='a'),))
        c=verify(p,q,[{'a':1,'b':3}])['counterexample'];self.assertEqual(c['original'],{'result':4});self.assertEqual(c['candidate'],{'result':2})
    def test_symbolic_limit_label(self):
        s='\n'.join(['t0 = a + b']+[f't{n} = t{n-1} * t{n-1}' for n in range(1,8)]+['result = t7'])
        p=parse(s,'tac',['result'])
        with self.assertRaises(SymbolicLimit):polynomials(p)
        self.assertIn('tests only',verify(p,p,[{'a':0,'b':0}])['method'])

class SearchTests(unittest.TestCase):
    def test_path_and_monotone_best(self):
        p=parse('def f(a,b):\n    x = a + 0\n    y = b * 1\n    unused = 10 + 20\n    return x + y')
        r=optimize(p,measure=False)
        self.assertLess(r['optimized_metrics']['static_cost'],r['original_metrics']['static_cost'])
        self.assertGreater(len(r['winning_path']),2)
        self.assertTrue(all(a['best_cost']>=b['best_cost'] for a,b in zip(r['history'],r['history'][1:])))
    def test_constant_return(self):
        r=optimize(parse('def f():\n    return 0'),measure=False)
        self.assertEqual(r['summary']['candidates'],0)
        self.assertEqual(r['optimized_metrics']['static_cost'],0)
    def test_limits_and_selection(self):
        p=parse('result = a + 0','tac');r=optimize(p,budget=1,enabled=['zero_add'],measure=False)
        self.assertLessEqual(r['summary']['candidates'],1)
        for kw in ({'enabled':[]},{'budget':99999}):
            with self.assertRaises(InputError):optimize(p,**kw)
    def test_timing(self):
        r=optimize(parse('result = a + 0','tac'),budget=5,runtime_weight=.01)
        self.assertGreater(r['timing']['original']['median_us'],0)
        self.assertEqual(len(r['timing']['selected']['batches_us']),7)
    def test_corpus(self):
        for seed in range(25):
            p=parse(generate(seed),'tac',['result']);r=optimize(p,budget=60,measure=False)
            self.assertTrue(r['validation']['valid'])
            self.assertLessEqual(r['optimized_metrics']['static_cost'],r['original_metrics']['static_cost'])

if __name__=='__main__':unittest.main()
