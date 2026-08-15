"""
Implementation Verification Script

Checks that all changes from the implementation plan are in place.
Run this before starting the backend to verify implementation correctness.

Usage:
    python verify_implementation.py
"""

import sys
from pathlib import Path

# Color codes for terminal output
GREEN = '\033[92m'
RED = '\033[91m'
YELLOW = '\033[93m'
RESET = '\033[0m'

def check_file_contains(filepath: str, search_strings: list[str], description: str) -> bool:
    """Check if a file contains all specified strings."""
    try:
        path = Path(filepath)
        if not path.exists():
            print(f"  {RED}✗{RESET} {description}: File not found: {filepath}")
            return False
        
        content = path.read_text(encoding='utf-8')
        missing = []
        for search_str in search_strings:
            if search_str not in content:
                missing.append(search_str)
        
        if missing:
            print(f"  {RED}✗{RESET} {description}: Missing content")
            for m in missing:
                print(f"      Missing: {m[:80]}...")
            return False
        
        print(f"  {GREEN}✓{RESET} {description}")
        return True
    except Exception as e:
        print(f"  {RED}✗{RESET} {description}: Error reading file: {e}")
        return False


def main():
    print(f"\n{YELLOW}{'='*70}{RESET}")
    print(f"{YELLOW}Implementation Verification - Debugging & Stabilization v3{RESET}")
    print(f"{YELLOW}{'='*70}{RESET}\n")
    
    checks_passed = 0
    checks_total = 0
    
    # ═══════════════════════════════════════════════════════════════════
    print("📦 CODING ROUND CHECKS")
    print("-" * 70)
    
    # Check 1: Schema separation
    checks_total += 1
    if check_file_contains(
        "app/schemas/coding.py",
        [
            "class CodingTestCaseResult(BaseModel):",
            "class CodingRunResponse(BaseModel):",
            "class CodingSubmissionResponse(BaseModel):",
            "test_case_results: List[CodingTestCaseResult]",
            "submission_id: int  # Required. Never null.",
            "submitted_at: datetime  # Required.",
        ],
        "Schema separation (CodingRunResponse vs CodingSubmissionResponse)"
    ):
        checks_passed += 1
    
    # Check 2: Code evaluator per-case results
    checks_total += 1
    if check_file_contains(
        "app/modules/coding/utils/code_evaluator.py",
        [
            "def _mock_evaluate(code: str, language: str, test_cases: List[CodingTestCase], visible_only: bool = True)",
            "test_case_results = []",
            'if visible_only:',
            'result["test_case_results"] = test_case_results',
        ],
        "Code evaluator per-case results"
    ):
        checks_passed += 1
    
    # Check 3: Coding router responses
    checks_total += 1
    if check_file_contains(
        "app/modules/coding/routers/coding_router.py",
        [
            "CodingRunResponse",
            "CodingSubmissionResponse",
            '@router.post("/run", response_model=CodingRunResponse)',
            '@router.post("/submit", response_model=CodingSubmissionResponse)',
            "submission.submitted_at",
        ],
        "Coding router response models"
    ):
        checks_passed += 1
    
    # ═══════════════════════════════════════════════════════════════════
    print("\n🔊 SARVAM TTS CHECKS")
    print("-" * 70)
    
    # Check 4: Sarvam diagnostic logging
    checks_total += 1
    if check_file_contains(
        "app/services/sarvam_service.py",
        [
            "import time",
            "logger.info(f\"Sarvam client ready:",
            'logger.info(f"TTS request: text_len={len(text)}',
            "t0 = time.monotonic()",
            'logger.info(f"TTS success: audios_count={len(response.audios)}, bytes={len(audio_bytes)}, latency=',
            'logger.error(f"Sarvam TTS failed: type={type(e).__name__}, status={status_code}',
        ],
        "Sarvam diagnostic logging"
    ):
        checks_passed += 1
    
    # Check 5: Frontend TTS error handling
    checks_total += 1
    if check_file_contains(
        "frontend/src/services/interviewService.js",
        [
            "let response;",
            "try {",
            "response = await api.post(",
            "} catch (err) {",
            "new TextDecoder().decode(err.response?.data)",
            "const byteLen = response.data?.byteLength ?? 0;",
            'if (!contentType.includes(\'audio\') || byteLen < 1000)',
        ],
        "Frontend TTS error handling"
    ):
        checks_passed += 1
    
    # ═══════════════════════════════════════════════════════════════════
    print("\n⚙️ SETTINGS & PYTEST CHECKS")
    print("-" * 70)
    
    # Check 6: Settings OPENAI_API_KEY optional
    checks_total += 1
    if check_file_contains(
        "app/config/settings.py",
        [
            "OPENAI_API_KEY: Optional[str] = None",
        ],
        "Settings OPENAI_API_KEY optional"
    ):
        checks_passed += 1
    
    # ═══════════════════════════════════════════════════════════════════
    print("\n🎤 INTERVIEW ROUND CHECKS")
    print("-" * 70)
    
    # Check 7: Interview model completion fields
    checks_total += 1
    if check_file_contains(
        "app/models/interview.py",
        [
            "status: Mapped[str] = mapped_column(String(20), server_default=\"ACTIVE\"",
            "completion_reason: Mapped[str | None] = mapped_column(",
            "String(30), nullable=True",
            "# ALL_QUESTIONS_COMPLETED | USER_SUBMITTED | TIME_EXPIRED",
            "completed_at: Mapped[datetime | None]",
        ],
        "Interview model completion fields"
    ):
        checks_passed += 1
    
    # Check 8: Migration file exists
    checks_total += 1
    if Path("alembic/versions/add_interview_completion_fields.py").exists():
        print(f"  {GREEN}✓{RESET} Migration file exists")
        checks_passed += 1
    else:
        print(f"  {RED}✗{RESET} Migration file missing: alembic/versions/add_interview_completion_fields.py")
    
    # Check 9: Interview complete endpoint
    checks_total += 1
    if check_file_contains(
        "app/modules/interview/routers/interview_router.py",
        [
            '@router.post("/session/{interview_id}/complete")',
            'async def complete_interview(',
            'if interview.status == "COMPLETED":',
            'interview.completion_reason = "USER_SUBMITTED"',
            "interview.completed_at = datetime.utcnow()",
        ],
        "Interview complete endpoint"
    ):
        checks_passed += 1
    
    # Check 10: Interview schema updates
    checks_total += 1
    if check_file_contains(
        "app/modules/interview/schemas/interview_schema.py",
        [
            "intent_score: Optional[float] = None",
            "completion_ratio: Optional[float] = None",
            "completion_reason: Optional[str] = None",
        ],
        "Interview report schema updates"
    ):
        checks_passed += 1
    
    # Check 11: Report endpoint updates
    checks_total += 1
    if check_file_contains(
        "app/modules/interview/routers/interview_router.py",
        [
            "intent_scores = [t.intent for t in main_turns if t.intent]",
            "completion_ratio = len(main_turns) / max(interview.total_turns, 1)",
            "completion_reason = interview.completion_reason",
            "intent_score=round(avg_intent, 2) if avg_intent is not None else None,",
            "completion_ratio=round(completion_ratio, 2),",
            "completion_reason=completion_reason,",
        ],
        "Report endpoint completion fields"
    ):
        checks_passed += 1
    
    # Check 12: Frontend proctoring hook fix
    checks_total += 1
    if check_file_contains(
        "frontend/src/pages/InterviewRoom.jsx",
        [
            "const interviewId = localStorage.getItem('interview_id');",
            "const proctoring = useAdvancedProctoring(",
            "interviewId ? parseInt(interviewId, 10) : null,",
        ],
        "Frontend proctoring hook fix"
    ):
        checks_passed += 1
    
    # Check 13: Audio lifecycle cleanup
    checks_total += 1
    if check_file_contains(
        "frontend/src/pages/InterviewRoom.jsx",
        [
            "if (audioContext.state === 'suspended') {",
            "await audioContext.resume();",
            "audioContextRef.current?.close();",
            "proctoring.stopMonitoring?.();",
        ],
        "Audio lifecycle cleanup"
    ):
        checks_passed += 1
    
    # Check 14: Submit interview button
    checks_total += 1
    if check_file_contains(
        "frontend/src/pages/InterviewRoom.jsx",
        [
            "const handleSubmitInterview = async () => {",
            "window.confirm(",
            "await api.post(`/interview/session/${interviewId}/complete`)",
            "navigate(`/interview/report/${interviewId}`);",
            "<button",
            "onClick={handleSubmitInterview}",
            "Submit Interview",
        ],
        "Submit interview button & handler"
    ):
        checks_passed += 1
    
    # ═══════════════════════════════════════════════════════════════════
    print(f"\n{YELLOW}{'='*70}{RESET}")
    print(f"\n📊 RESULTS: {checks_passed}/{checks_total} checks passed")
    
    if checks_passed == checks_total:
        print(f"\n{GREEN}✅ All implementation checks passed!{RESET}")
        print(f"{GREEN}Ready to apply migration and start testing.{RESET}\n")
        return 0
    else:
        print(f"\n{RED}❌ {checks_total - checks_passed} check(s) failed.{RESET}")
        print(f"{RED}Review the failed checks above and verify implementation.{RESET}\n")
        return 1


if __name__ == "__main__":
    sys.exit(main())
