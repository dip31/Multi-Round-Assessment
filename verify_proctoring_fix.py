"""
Quick verification script for proctoring system fixes.

This script checks that all the fixes are in place and the system
is ready for testing.
"""

import os
import re


def check_file_content(filepath, patterns, description):
    """Check if file contains expected patterns."""
    print(f"\n{'='*60}")
    print(f"Checking: {description}")
    print(f"File: {filepath}")
    print(f"{'='*60}")
    
    if not os.path.exists(filepath):
        print(f"❌ File not found: {filepath}")
        return False
    
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()
    
    all_found = True
    for pattern_desc, pattern in patterns:
        if re.search(pattern, content, re.MULTILINE | re.DOTALL):
            print(f"✅ {pattern_desc}")
        else:
            print(f"❌ {pattern_desc}")
            all_found = False
    
    return all_found


def main():
    print("=" * 60)
    print("PROCTORING SYSTEM FIX VERIFICATION")
    print("=" * 60)
    
    all_checks_passed = True
    
    # Check 1: useAdvancedProctoring hook exposes startMonitoring
    all_checks_passed &= check_file_content(
        "frontend/src/hooks/useAdvancedProctoring.js",
        [
            ("initializeProctoring function exists", r"const\s+initializeProctoring\s*=\s*useCallback"),
            ("startMonitoring alias exposed", r"startMonitoring:\s*initializeProctoring"),
            ("stopMonitoring exposed", r"stopMonitoring[,\s]"),
            ("videoRef exposed", r"videoRef[,\s]"),
        ],
        "Hook exposes startMonitoring function"
    )
    
    # Check 2: Frame capture uses correct endpoint
    all_checks_passed &= check_file_content(
        "frontend/src/hooks/useAdvancedProctoring.js",
        [
            ("Frame capture function exists", r"const\s+captureAndAnalyzeFrame\s*=\s*useCallback"),
            ("Uses correct endpoint", r"\/advanced-proctoring\/analyze-frame"),
            ("Includes session_id parameter", r"\?session_id=\$\{sessionId\}"),
        ],
        "Frame capture uses correct endpoint"
    )
    
    # Check 3: Backend has analyze-frame endpoint
    all_checks_passed &= check_file_content(
        "app/modules/advanced_proctoring/routers/advanced_proctoring_router.py",
        [
            ("Endpoint exists", r'@router\.post\("/analyze-frame"\)'),
            ("Validates AssessmentSession", r"AssessmentSession"),
            ("Function signature correct", r"async\s+def\s+analyze_frame_general"),
            ("Phone detection service imported", r"from\s+app\.services\.phone_detection_service\s+import\s+detect_phones"),
        ],
        "Backend has analyze-frame endpoint"
    )
    
    # Check 4: CodingRoundV2 proctoring integration
    all_checks_passed &= check_file_content(
        "frontend/src/pages/CodingRoundV2.jsx",
        [
            ("Imports useAdvancedProctoring", r"import.*useAdvancedProctoring"),
            ("Destructures startMonitoring", r"startMonitoring"),
            ("useEffect depends on sessionId", r"useEffect.*\[\s*sessionId\s*\]"),
            ("Calls startMonitoring", r"startMonitoring\?\.\(\)"),
            ("Violation callback defined", r"useAdvancedProctoring\(sessionId,\s*\(violation\)\s*=>"),
        ],
        "CodingRoundV2 proctoring integration"
    )
    
    # Check 5: Database models properly linked
    all_checks_passed &= check_file_content(
        "app/models/assessment.py",
        [
            ("advanced_proctoring_events relationship", r"advanced_proctoring_events.*relationship"),
            ("AdvancedProctoringEvent imported", r"AdvancedProctoringEvent"),
        ],
        "Database models properly linked"
    )
    
    # Check 6: Advanced proctoring model exists
    all_checks_passed &= check_file_content(
        "app/models/advanced_proctoring.py",
        [
            ("AdvancedProctoringEvent class", r"class\s+AdvancedProctoringEvent"),
            ("session_id column", r"session_id.*ForeignKey"),
            ("event_type column", r"event_type.*String"),
            ("confidence column", r"confidence.*Float"),
            ("event_metadata column", r"event_metadata.*JSON"),
            ("ADVANCED_PROCTORING_EVENTS dict", r"ADVANCED_PROCTORING_EVENTS\s*="),
            ("VIOLATION_RISK_SCORES dict", r"VIOLATION_RISK_SCORES\s*="),
        ],
        "Advanced proctoring model"
    )
    
    # Check 7: Proctoring service exists
    all_checks_passed &= check_file_content(
        "app/services/advanced_proctoring_service.py",
        [
            ("AdvancedProctoringService class", r"class\s+AdvancedProctoringService"),
            ("log_advanced_event method", r"def\s+log_advanced_event"),
            ("get_session_proctoring_summary method", r"def\s+get_session_proctoring_summary"),
            ("check_violation_thresholds method", r"def\s+check_violation_thresholds"),
            ("Service instance exported", r"advanced_proctoring_service\s*="),
        ],
        "Advanced proctoring service"
    )
    
    # Check 8: Phone detection service exists
    if os.path.exists("app/services/phone_detection_service.py"):
        all_checks_passed &= check_file_content(
            "app/services/phone_detection_service.py",
            [
                ("detect_phones function", r"def\s+detect_phones"),
                ("YOLO model loading", r"YOLO|yolo"),
            ],
            "Phone detection service"
        )
    else:
        print("\n⚠️  Phone detection service not found (optional feature)")
    
    # Check 9: YOLO model file exists
    print("\n" + "="*60)
    print("Checking: YOLO model file")
    print("="*60)
    if os.path.exists("yolov8n.pt"):
        print("✅ YOLO model file exists (yolov8n.pt)")
    else:
        print("⚠️  YOLO model file not found (download from ultralytics)")
        print("   Phone detection will not work without this file")
    
    # Final summary
    print("\n" + "="*60)
    print("VERIFICATION SUMMARY")
    print("="*60)
    
    if all_checks_passed:
        print("✅ All critical checks passed!")
        print("\nThe proctoring system is ready for testing.")
        print("\nNext steps:")
        print("1. Start the backend: uvicorn app.main:app --reload --port 8000")
        print("2. Start the frontend: cd frontend && npm run dev")
        print("3. Start a coding round and test tab switching")
        print("4. See test_proctoring_features.md for full test guide")
    else:
        print("❌ Some checks failed!")
        print("\nPlease review the failed checks above and fix any issues.")
        print("The system may not work correctly until all checks pass.")
    
    print("="*60)
    
    return all_checks_passed


if __name__ == "__main__":
    success = main()
    exit(0 if success else 1)
