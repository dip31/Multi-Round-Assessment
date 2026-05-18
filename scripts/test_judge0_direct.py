"""
Test Judge0 directly to verify it's working
"""
import requests
import json
import time

JUDGE0_URL = "http://localhost:2358"

def test_judge0():
    print("Testing Judge0 directly...")
    
    # Simple Python code to count vowels
    code = """s = input()
vowels = 'aeiouAEIOU'
count = sum(1 for c in s if c in vowels)
print(count)"""
    
    payload = {
        "source_code": code,
        "language_id": 71,  # Python 3
        "stdin": "Hello World"
    }
    
    print("\nSubmitting to Judge0...")
    print(f"Code:\n{code}\n")
    print(f"Input: Hello World")
    print(f"Expected output: 3\n")
    
    try:
        # Submit with wait=true
        response = requests.post(
            f"{JUDGE0_URL}/submissions",
            json=payload,
            params={"wait": "true"},
            headers={"Content-Type": "application/json"},
            timeout=30
        )
        
        print(f"Status Code: {response.status_code}")
        
        if response.status_code == 201:
            result = response.json()
            print("\nJudge0 Response:")
            print(json.dumps(result, indent=2))
            
            print("\n" + "=" * 60)
            print("PARSED RESULTS:")
            print("=" * 60)
            print(f"Status ID: {result.get('status', {}).get('id')}")
            print(f"Status Description: {result.get('status', {}).get('description')}")
            print(f"Stdout: {repr(result.get('stdout'))}")
            print(f"Stderr: {repr(result.get('stderr'))}")
            print(f"Compile Output: {repr(result.get('compile_output'))}")
            print(f"Time: {result.get('time')}")
            print(f"Memory: {result.get('memory')}")
            
            if result.get('stdout'):
                print(f"\n✓ Got output: {result['stdout'].strip()}")
            else:
                print("\n✗ No stdout received!")
                
        else:
            print(f"Error: {response.text}")
    
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_judge0()
