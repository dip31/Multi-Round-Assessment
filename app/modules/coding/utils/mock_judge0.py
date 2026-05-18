"""
Mock Judge0 Client for Windows Testing

Use this when Judge0 Docker has cgroup issues on Windows.
Returns simulated execution results for testing the UI.
"""

def mock_submit_code(source_code: str, language_id: int, stdin: str) -> dict:
    """
    Simulate Judge0 execution for testing purposes.
    Actually executes Python code and captures output.
    """
    
    if language_id == 71:  # Python
        try:
            import io
            import sys
            from contextlib import redirect_stdout, redirect_stderr
            
            # Capture stdout and stderr
            stdout_capture = io.StringIO()
            stderr_capture = io.StringIO()
            
            # Prepare stdin
            old_stdin = sys.stdin
            sys.stdin = io.StringIO(stdin) if stdin else io.StringIO("")
            
            # Create a namespace with builtins and common imports
            namespace = {
                "__builtins__": __builtins__,
                "input": lambda: sys.stdin.readline().rstrip('\n'),
            }
            
            try:
                with redirect_stdout(stdout_capture), redirect_stderr(stderr_capture):
                    exec(source_code, namespace)
            finally:
                sys.stdin = old_stdin
            
            stdout_output = stdout_capture.getvalue()
            stderr_output = stderr_capture.getvalue()
            
            # If there was stderr, treat as runtime error
            if stderr_output:
                return {
                    "stdout": stdout_output,
                    "stderr": stderr_output,
                    "compile_output": None,
                    "status": {"id": 11, "description": "Runtime Error"},
                    "time": "0.05",
                    "memory": 2048
                }
            
            # Success
            return {
                "stdout": stdout_output,
                "stderr": None,
                "compile_output": None,
                "status": {"id": 3, "description": "Accepted"},
                "time": "0.05",
                "memory": 2048
            }
            
        except SyntaxError as e:
            return {
                "stdout": None,
                "stderr": None,
                "compile_output": str(e),
                "status": {"id": 6, "description": "Compilation Error"},
                "time": "0.01",
                "memory": 1024
            }
        except Exception as e:
            return {
                "stdout": None,
                "stderr": str(e),
                "compile_output": None,
                "status": {"id": 11, "description": "Runtime Error"},
                "time": "0.05",
                "memory": 2048
            }
    
    # For C++ (54) and Java (62), return placeholder
    return {
        "stdout": "",
        "stderr": None,
        "compile_output": None,
        "status": {"id": 3, "description": "Accepted"},
        "time": "0.1",
        "memory": 4096
    }
