#!/usr/bin/env python
"""Quick test of mock Judge0 functionality"""

from app.modules.coding.utils.mock_judge0 import mock_submit_code

# Test 1: Simple print
print("=" * 50)
print("Test 1: Simple print statement")
code1 = """
print("Hello World")
"""
result1 = mock_submit_code(code1, 71, "")
print(f"Code: {code1.strip()}")
print(f"Result stdout: {repr(result1['stdout'])}")
print(f"Result status: {result1['status']}")
print()

# Test 2: Read input and print
print("=" * 50)
print("Test 2: Read input and print sum")
code2 = """
a = int(input())
b = int(input())
print(a + b)
"""
stdin2 = "5\n3"
result2 = mock_submit_code(code2, 71, stdin2)
print(f"Code: {code2.strip()}")
print(f"Stdin: {repr(stdin2)}")
print(f"Result stdout: {repr(result2['stdout'])}")
print(f"Result status: {result2['status']}")
print()

# Test 3: Loop
print("=" * 50)
print("Test 3: Loop that prints numbers")
code3 = """
n = int(input())
for i in range(1, n + 1):
    print(i)
"""
stdin3 = "3"
result3 = mock_submit_code(code3, 71, stdin3)
print(f"Code: {code3.strip()}")
print(f"Stdin: {repr(stdin3)}")
print(f"Result stdout: {repr(result3['stdout'])}")
print(f"Result status: {result3['status']}")
print()

# Test 4: Error case
print("=" * 50)
print("Test 4: Syntax error")
code4 = """
print("hello
"""
result4 = mock_submit_code(code4, 71, "")
print(f"Code: {code4.strip()}")
print(f"Result compile_output: {repr(result4['compile_output'])}")
print(f"Result status: {result4['status']}")
