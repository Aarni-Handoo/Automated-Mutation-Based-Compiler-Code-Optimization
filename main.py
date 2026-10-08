import argparse
from pathlib import Path
from optimizer import execute, metrics, optimize


def main():
    parser = argparse.ArgumentParser(description='Mutation-based TAC optimizer: stage 1')
    parser.add_argument('file', nargs='?', type=Path,
                        default=Path(__file__).parent / 'examples' / 'demo.tac')
    args = parser.parse_args()
    try:
        result = optimize(args.file.read_text(encoding='utf-8'))
    except (OSError, ValueError) as error:
        parser.exit(1, f'Error: {error}\n')

    print('AUTOMATED MUTATION-BASED COMPILER CODE OPTIMIZATION')
    print('Stage 1 - backend prototype\n')
    print('Original TAC')
    for instruction in result['original']:
        print(' ', instruction)
    print('\nCandidate search (one round, up to two mutations per candidate)')
    print(f'{"ID":<5}{"Cost":<9}{"Check":<8}Mutations')
    for row in result['candidates']:
        check = 'PASS' if row['passed'] else 'FAIL'
        print(f'{row["id"]:<5}{row["cost"]:<9.2f}{check:<8}{row["mutations"]}')
    if not result['candidates']:
        print('No distinct changed candidates. Keeping the original.')
    print('\nBest TAC found')
    for instruction in result['best']:
        print(' ', instruction)
    before, after = metrics(result['original']), metrics(result['best'])
    print('\nMetric             Original   Selected')
    for key in ('instructions', 'arithmetic', 'temporaries', 'cost'):
        print(f'{key:<19}{before[key]:<11}{after[key]}')
    reduction = 100 * (before['cost'] - after['cost']) / before['cost']
    print(f'Static cost reduction: {reduction:.2f}%')
    print(f'Validation: {result["test_count"]} input cases per candidate (not a formal proof).')
    inputs = {name: index + 3 for index, name in enumerate(result['inputs'])}
    print('\nExample execution')
    print('Inputs:   ', inputs)
    print('Original: ', execute(result['original'], inputs, result['outputs']))
    print('Selected: ', execute(result['best'], inputs, result['outputs']))
    print('\nPending: 4+ more operators, iterative search, runtime scoring, 200-500 program benchmark.')


if __name__ == '__main__':
    main()
