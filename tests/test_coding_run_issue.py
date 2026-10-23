"""
Quick test to identify the coding run issue
"""
import sys

# Check if the issue is:
# 1. "no active coding round" - 404
# 2. "problem not assigned to current round" - 400
# 3. "coding round has expired" - 400

print("Possible causes for 400 Bad Request in /api/v1/coding/run:")
print()
print("1. Problem not assigned to current round")
print("   - The problem_id in the request doesn't match any SessionProblem for this round")
print("   - Check: Does startRound() properly assign problems?")
print()
print("2. Coding round has expired")
print("   - The round started_at + time_limit has passed")
print("   - Check: Is the time limit too short?")
print()
print("3. Missing or invalid payload fields")
print("   - problem_id, code, or language missing/invalid")
print()
print("To debug, check the backend terminal for the actual error message.")
print("The 400 response should include a 'detail' field with the specific error.")
print()
print("Common fixes:")
print("- Ensure startRound() is called and completes successfully")
print("- Verify problem assignment happens in startRound()")
print("- Check that payload includes: problem_id, code, language")
