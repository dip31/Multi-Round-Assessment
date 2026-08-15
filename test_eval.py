from app.modules.coding.utils.code_evaluator import evaluate_submission

class MockTC:
    def __init__(self, input_data, expected_output, is_hidden=False):
        self.input_data = input_data
        self.expected_output = expected_output
        self.is_hidden = is_hidden

test_cases = [
    MockTC('1 2', '3'),
    MockTC('5 5', '10'),
]

code = """def solve():
    a, b = map(int, input().split())
    print(a + b)

if __name__ == "__main__":
    solve()"""

result = evaluate_submission(code, 'python', test_cases, visible_only=False)
print('Status:', result.get('status'))
print('Score:', result.get('score'))
print('Passed:', result.get('test_cases_passed'))
print('Total:', result.get('total_test_cases'))
print('Error:', result.get('error_message'))
print('Compile:', result.get('compile_output'))
print('Stderr:', result.get('stderr'))