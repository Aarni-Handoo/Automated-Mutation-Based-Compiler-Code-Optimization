# Automated Mutation-Based Compiler Code Optimization

Stage 1 backend prototype. This is roughly the first half of the planned project,
not the finished optimizer. There is no frontend or web server in this version.

## Run in VS Code

1. Extract the ZIP and open the `mutation_optimizer` folder in VS Code.
2. Open Terminal > New Terminal.
3. Run `python main.py` (on Windows, `py main.py` also works).
4. Edit `examples/demo.tac`, save it, and run again.

Python 3.10 or newer is required. No external packages are needed.

Other commands:

```sh
python main.py examples/strength.tac
python main.py path/to/your_program.tac
python -m unittest -v
```

`sample_output.txt` contains actual output captured from the default demo.

## What is implemented

- Parser and interpreter for straight-line integer TAC: assignments, +, -, *.
- Four mutations: constant folding, zero-add removal, one-mul removal,
  and strength reduction (x * 2 becomes x + x).
- One candidate-search round using single operators and ordered pairs.
- Duplicate candidates are skipped. Lowest-cost passing candidate wins;
  the original is kept if none improves it.
- Candidate checks using 5 boundary-style cases and 20 seeded random cases.
- Terminal output showing candidates, costs, selected TAC, and example execution.

## Current cost

`cost = instructions + 2 * arithmetic_operations + 1.2 * temporary_count`

This is a static score, not a runtime or speedup measurement. Execution time is
not part of this stage. Addition and multiplication have equal weights, so
strength reduction alone ties the original cost and is not selected on a tie.
An instruction-count reduction is not expected from the current four operators.

## Input rules

One assignment per line; semicolons are optional. Operands are integer literals
or variable names. `#` and `//` comments are allowed. Values read before assignment
are inputs. All assigned names except `t` followed by digits are observable outputs.
`t1`, `t2`, etc. are reserved temporaries. `total` is a normal output name.
Include at least one named output, e.g. `result = t4`.

This stage deliberately rejects declarations, branches, loops, division,
floats, nested expressions, C source, and print statements.

## Next stage

- Implement at least four additional operators with reassignment safety:
  constant propagation, copy propagation, common subexpression elimination,
  and dead-code elimination.
- Repeat candidate generation across iterations and track exploration depth.
- Add fair execution-time measurements for original and candidate programs.
- Add independent validation and broader edge-case tests.
- Evaluate 200-500 programs; record correctness/validity rates and cost reduction.
- Add a basic interface only after the backend is ready.

## Demonstration order

Open `examples/demo.tac`, then run `python main.py`. Point out the candidate table,
the lower static cost, and matching example outputs. Show `mutate()` for the four
transformations and `optimize()` for selection. State that search is currently
one round and runtime measurement/large benchmarks are still pending.

Passing the finite input checks is not a proof of equivalence. No final benchmark
claims or completion percentage measurements are included.
