#!/usr/bin/env python
"""Direct test of Judge0 API"""

import requests
import json

JUDGE0_URL = "http://localhost:2358"

# Test 1: Check if Judge0 is reachable
print("=" * 60)
print("Test 1: Check Judge0 Health")
try:
    response = requests.get(f"{JUDGE0_URL}/health", timeout=5)
    print(f"Status: {response.status_code}")
    print(f"Response: {response.text}")
except Exception as e:
    print(f"ERROR: {e}")

# Test 2: Get supported languages
print("\n" + "=" * 60)
print("Test 2: Get Supported Languages")
try:
    response = requests.get(f"{JUDGE0_URL}/languages", timeout=5)
    print(f"Status: {response.status_code}")
    languages = response.json()
    python_langs = [l for l in languages if 'python' in l['name'].lower()]
    print(f"Found {len(python_langs)} Python versions:")
    for lang in python_langs[:3]:
        print(f"  ID {lang['id']}: {lang['name']}")
except Exception as e:
    print(f"ERROR: {e}")

# Test 3: Submit simple Python code
print("\n" + "=" * 60)
print("Test 3: Submit Code - print('hello')")
try:
    payload = {
        "source_code": "print('hello')",
        "language_id": 71,
        "stdin": ""
    }
    print(f"Sending: {json.dumps(payload, indent=2)}")
    
    response = requests.post(
        f"{JUDGE0_URL}/submissions",
        json=payload,
        params={"wait": "true"},
        headers={"Content-Type": "application/json"},
        timeout=30
    )
    print(f"Status: {response.status_code}")
    result = response.json()
    print(f"Response:")
    print(json.dumps(result, indent=2))
    
    print(f"\nExtracted values:")
    print(f"  Status ID: {result.get('status', {}).get('id')}")
    print(f"  Status Description: {result.get('status', {}).get('description')}")
    print(f"  Stdout: {repr(result.get('stdout'))}")
    print(f"  Stderr: {repr(result.get('stderr'))}")
    print(f"  Compile Output: {repr(result.get('compile_output'))}")
    
except Exception as e:
    print(f"ERROR: {e}")
    import traceback
    traceback.print_exc()

# Test 4: Submit code with input
print("\n" + "=" * 60)
print("Test 4: Submit Code - Read 2 numbers and print sum")
code = """a = int(input())
b = int(input())
print(a + b)"""

try:
    payload = {
        "source_code": code,
        "language_id": 71,
        "stdin": "5\n3"
    }
    print(f"Code:")
    print(code)
    print(f"\nStdin: {repr('5\\n3')}")
    
    response = requests.post(
        f"{JUDGE0_URL}/submissions",
        json=payload,
        params={"wait": "true"},
        headers={"Content-Type": "application/json"},
        timeout=30
    )
    print(f"\nStatus: {response.status_code}")
    result = response.json()
    print(f"Response:")
    print(json.dumps(result, indent=2))
    
    print(f"\nExtracted values:")
    stdout = result.get('stdout')
    print(f"  Stdout: {repr(stdout)}")
    print(f"  Expected: {repr('8')}")
    if stdout:
        print(f"  Match: {stdout.strip() == '8'}")
    else:
        print(f"  Match: False (stdout is None)")
    
except Exception as e:
    print(f"ERROR: {e}")
    import traceback
    traceback.print_exc()
