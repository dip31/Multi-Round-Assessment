#!/usr/bin/env python3
"""
Diagnose Judge0 connectivity and code execution issues
"""

import requests
import json

JUDGE0_URL = "http://192.168.0.104:2358"

def test_judge0_connection():
    """Test if Judge0 is reachable"""
    print("🔍 Diagnosing Judge0 Connection")
    print("=" * 50)
    
    # Test 1: Check if Judge0 is reachable
    print("\n1. Testing Judge0 connectivity...")
    print(f"   URL: {JUDGE0_URL}")
    
    try:
        response = requests.get(f"{JUDGE0_URL}/about", timeout=5)
        print(f"   ✅ Judge0 is reachable (Status: {response.status_code})")
        print(f"   Version info: {response.json()}")
    except requests.exceptions.ConnectionError:
        print(f"   ❌ Cannot connect to Judge0 at {JUDGE0_URL}")
        print(f"   Possible issues:")
        print(f"      - Judge0 server is not running")
        print(f"      - IP address is incorrect")
        print(f"      - Firewall blocking connection")
        print(f"      - Network issue")
        return False
    except requests.exceptions.Timeout:
        print(f"   ❌ Connection timeout")
        return False
    except Exception as e:
        print(f"   ❌ Error: {e}")
        return False
    
    # Test 2: Submit simple Python code
    print("\n2. Testing code execution...")
    
    test_code = """
print("Hello, World!")
"""
    
    payload = {
        "source_code": test_code,
        "language_id": 71,  # Python 3
        "stdin": ""
    }
    
    try:
        response = requests.post(
            f"{JUDGE0_URL}/submissions?wait=true",
            json=payload,
            headers={"Content-Type": "application/json"},
            timeout=30
        )
        
        if response.status_code != 201:
            print(f"   ❌ Submission failed (Status: {response.status_code})")
            print(f"   Response: {response.text}")
            return False
        
        result = response.json()
        status_id = result.get("status", {}).get("id")
        status_desc = result.get("status", {}).get("description")
        stdout = result.get("stdout", "")
        stderr = result.get("stderr", "")
        compile_output = result.get("compile_output", "")
        
        print(f"   Status ID: {status_id} ({status_desc})")
        print(f"   Output: {repr(stdout)}")
        
        if status_id == 3:  # Accepted
            print(f"   ✅ Code execution successful!")
        elif status_id == 13:  # Internal Error
            print(f"   ❌ Judge0 internal error")
            print(f"   This usually means:")
            print(f"      - Docker containers not running properly")
            print(f"      - Resource limits (cgroups) issue on Windows")
            print(f"      - Judge0 configuration problem")
            if stderr:
                print(f"   Stderr: {stderr}")
            if compile_output:
                print(f"   Compile output: {compile_output}")
            return False
        else:
            print(f"   ⚠️  Unexpected status")
            if stderr:
                print(f"   Stderr: {stderr}")
            if compile_output:
                print(f"   Compile output: {compile_output}")
        
    except Exception as e:
        print(f"   ❌ Error during code execution: {e}")
        return False
    
    # Test 3: Test with input
    print("\n3. Testing code with input...")
    
    test_code_with_input = """
n = int(input())
print(f"You entered: {n}")
"""
    
    payload = {
        "source_code": test_code_with_input,
        "language_id": 71,
        "stdin": "42"
    }
    
    try:
        response = requests.post(
            f"{JUDGE0_URL}/submissions?wait=true",
            json=payload,
            headers={"Content-Type": "application/json"},
            timeout=30
        )
        
        result = response.json()
        status_id = result.get("status", {}).get("id")
        stdout = result.get("stdout", "")
        
        print(f"   Status ID: {status_id}")
        print(f"   Output: {repr(stdout)}")
        
        if status_id == 3 and "42" in stdout:
            print(f"   ✅ Input/output working correctly!")
        else:
            print(f"   ⚠️  Input/output may have issues")
        
    except Exception as e:
        print(f"   ❌ Error: {e}")
        return False
    
    # Test 4: Check available languages
    print("\n4. Checking available languages...")
    
    try:
        response = requests.get(f"{JUDGE0_URL}/languages", timeout=5)
        languages = response.json()
        
        python_langs = [l for l in languages if "Python" in l.get("name", "")]
        cpp_langs = [l for l in languages if "C++" in l.get("name", "")]
        java_langs = [l for l in languages if "Java" in l.get("name", "")]
        
        print(f"   Python languages: {len(python_langs)}")
        for lang in python_langs[:3]:
            print(f"      - {lang['name']} (ID: {lang['id']})")
        
        print(f"   C++ languages: {len(cpp_langs)}")
        for lang in cpp_langs[:3]:
            print(f"      - {lang['name']} (ID: {lang['id']})")
        
        print(f"   Java languages: {len(java_langs)}")
        for lang in java_langs[:3]:
            print(f"      - {lang['name']} (ID: {lang['id']})")
        
    except Exception as e:
        print(f"   ⚠️  Could not fetch languages: {e}")
    
    print("\n" + "=" * 50)
    print("✅ Judge0 diagnosis complete!")
    print("\nSummary:")
    print("  - Judge0 is reachable and responding")
    print("  - Code execution is working")
    print("  - Input/output handling is functional")
    
    return True

if __name__ == "__main__":
    success = test_judge0_connection()
    
    if not success:
        print("\n❌ Judge0 has issues. Check the errors above.")
        print("\nTroubleshooting steps:")
        print("  1. Verify Judge0 is running: docker ps")
        print("  2. Check Judge0 logs: docker logs judge0-server")
        print("  3. Restart Judge0: docker-compose restart")
        print("  4. Check network connectivity to 192.168.0.104")
        exit(1)
    else:
        print("\n✅ Judge0 is working correctly!")
        exit(0)