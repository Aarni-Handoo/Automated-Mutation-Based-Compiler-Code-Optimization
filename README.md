# **Automated Mutation-Based Compiler Code Optimization**

## A backend project that explores alternative versions of three-address code (TAC), checks their outputs, and selects a lower-cost candidate. The goal is to optimize a program by generating and evaluating different versions of it. Each version is created using small code transformations called mutations.
For example:

t1 = a + 0       becomes       t1 = a

t2 = b * 1       becomes       t2 = b

t3 = 10 + 20     becomes       t3 = 30

The system compares the candidates against the original program on test inputs, scores them, and selects the lowest-cost candidate that passes those checks. The original is retained if no candidate improves its cost.
This project operates on a small TAC language. It is not a complete compiler for C, C++, or Python.
### How It Works
1. Parse: Convert the input TAC into instruction objects.
2. Generate: Apply individual mutation operators and ordered pairs of operators.
3. Filter: Skip unchanged and duplicate candidates.
4. Validate: Compare original and candidate outputs on a fixed set of test inputs.
5. Score: Calculate a weighted static cost for each candidate.
6. Select: Return the lowest-cost passing candidate found in the search. 
7. Display: Print the candidate table, selected TAC, cost comparison, and example outputs.
The current version performs one search round with at most two operator applications per candidate. Repeated search across generations is a future task.
Task Breakdown and Progress

Task 1: TAC Representation and Execution
- [x] Define an instruction representation.
- [x] Parse assignments and integer arithmetic using +, -, and *.
- [x] Support optional trailing semicolons and comments.
- [x] Identify input variables and observable output variables.
- [x] Execute supported TAC with a small interpreter.
- [x] Reject unsupported syntax with an error message.
- [ ] Extend the language to support additional operations.
- [ ] Add control-flow support and analysis for branches and loops.
Task 2: Mutation Operators
Four operators are implemented. The target is at least eight.
- [x] Constant folding: t1 = 10 + 20 → t1 = 30.
- [x] Zero-add removal: t1 = a + 0 → t1 = a.
- [x] One-mul removal: t1 = b * 1 → t1 = b.
- [x] Strength reduction: t1 = x * 2 → t1 = x + x.
- [ ] Constant propagation: Substitute known constant values safely.
- [ ] Copy propagation: Replace copied variables where reassignment permits it.
- [ ] Common subexpression elimination: Reuse available expression results.
- [ ] Dead-code elimination: Remove temporary calculations that are not needed.
- [ ] Safe instruction reordering: Reorder independent instructions.
Task 3: Candidate Search and Selection
- [x] Generate candidates using single mutations and ordered pairs.
- [x] Remove duplicate candidate programs.
- [x] Compare passing candidates by cost.
- [x] Keep the original when no candidate has a lower cost.
- [ ] Extend the search across multiple iterations.
- [ ] Add configurable pool size, iteration limits, and search strategy.
- [ ] Track exploration depth and candidate history across iterations.
Task 4: Correctness Checking
- [x] Compare observable outputs of original and candidate programs.
- [x] Check each distinct candidate against 25 input cases.
- [x] Use five fixed-value cases and 20 seeded random cases.
- [x] Include unit tests for independent demo inputs, reassignment, negative numbers, output naming, strength reduction, and unsupported syntax.
- [ ] Add a separate final-validation input set to the optimizer.
- [ ] Expand automated tests as new operators are implemented.
- [ ] Add branch-sensitive checks when control flow is supported.
Note: Passing a finite set of inputs is evidence of correctness, not a formal proof of equivalence.
Task 5: Cost Evaluation
- [x] Count instructions.
- [x] Count arithmetic operations.
- [x] Count distinct temporary variables assigned by the program.
- [x] Calculate static weighted cost and percentage reduction.
- [ ] Measure original and candidate execution times under comparable conditions.
- [ ] Add execution time to the cost function.
- [ ] Make weights configurable from the command line.
Task 6: Benchmarking and Results
- [x] Provide runnable demonstration programs.
- [x] Include captured terminal output from the default example.
- [ ] Build a diverse benchmark set of 200–500 programs.
- [ ] Define and report correctness rate and validity rate.
- [ ] Report exploration depth and aggregate cost reduction.
- [ ] Export benchmark results to CSV or JSON.
- [ ] Analyse results and document limitations.
Task 7: Demonstration and Documentation
- [x] Provide a command-line entry point for VS Code demonstrations.
- [x] Display candidate costs and validation results.
- [x] Display original and selected TAC.
- [x] Show matching outputs for an example input.
- [x] Document setup, input syntax, and remaining work.
- [ ] Add a minimal frontend after the backend is complete, if required.
- [ ] Prepare the final project report using measured benchmark results.

### Current Cost Function

```text
Cost = instruction_count
     + 2 × arithmetic_operation_count
     + 1.2 × temporary_variable_count
```

This is a static cost score, not an execution-time measurement. A lower score does not establish a real runtime speedup.

The planned full cost function is:

```text
Cost = w1 × instruction_count
     + w2 × arithmetic_operation_count
     + w3 × temporary_variable_count
     + w4 × execution_time
```

### Project Structure

- optimizer.py — Parser, interpreter, mutations, validation, and search
- main.py — Terminal demonstration
- test_optimizer.py — Backend unit tests
- requirements.txt — Python requirements
- README.md — Project documentation
- sample_output.txt — Captured demo output
- examples/demo.tac — Main optimization example
- examples/strength.tac — Strength-reduction example
