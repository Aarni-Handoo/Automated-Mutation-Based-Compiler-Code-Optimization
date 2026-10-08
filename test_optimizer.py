import unittest
from optimizer import parse, optimize, execute, metrics, mutate


class BackendTests(unittest.TestCase):
    def test_demo_preserves_outputs_on_independent_inputs(self):
        result = optimize('t1 = a + 0\nt2 = b * 1\nt3 = 10 + 20\nt4 = t1 + t2\nresult = t4 + t3')
        for a in (-1000, 0, 1234):
            for b in (-999, 2, 500):
                case = {'a': a, 'b': b}
                self.assertEqual(execute(result['best'], case, ['result']), {'result': a + b + 30})
        self.assertLess(metrics(result['best'])['cost'], metrics(result['original'])['cost'])

    def test_total_is_an_output_and_unchanged_cost_is_equal(self):
        result = optimize('total = x - 3')
        self.assertEqual(result['outputs'], ['total'])
        self.assertEqual(metrics(result['best']), metrics(result['original']))

    def test_reassignment_and_negative_numbers(self):
        result = optimize('x = -2\nx = x * 1\nt1 = -3 * -4\nresult = x + t1')
        self.assertEqual(execute(result['best'], {}, ['x', 'result']), {'x': -2, 'result': 10})

    def test_strength_reduction(self):
        code = parse('result = 2 * x')
        candidate = mutate(code, 'Strength reduction')
        self.assertEqual(str(candidate[0]), 'result = x + x')
        self.assertEqual(execute(candidate, {'x': -7}, ['result']), {'result': -14})

    def test_unsupported_input_is_rejected(self):
        for source in ('print(x)', 'goto L', 'result = a / b', 'result = a + b + c', ''):
            with self.assertRaises(ValueError):
                parse(source)
        with self.assertRaises(ValueError):
            optimize('t1 = x + 0')


if __name__ == '__main__':
    unittest.main()
