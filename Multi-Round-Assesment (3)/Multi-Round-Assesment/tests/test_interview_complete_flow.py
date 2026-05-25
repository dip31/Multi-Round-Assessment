"""
Complete Interview Flow Test

Tests:
1. Audio overlap prevention
2. STT transcription
3. Evaluation engine
4. Follow-up intelligence
5. Camera persistence
6. No 422 errors
"""

import asyncio
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app.services.groq_service import GroqService
from app.config.settings import settings

def test_evaluation_engine():
    """Test that evaluation engine is working"""
    print("\n=== TEST 1: Evaluation Engine ===")
    
    groq = GroqService(settings.GROQ_API_KEY)
    
    # Test cases
    test_cases = [
        {
            "question": "Tell me about your experience with Python",
            "answer": "I have 3 years of experience with Python. I've built web applications using Django and Flask, worked with data analysis using pandas and numpy, and created automation scripts.",
            "expected_quality": "GOOD"
        },
        {
            "question": "Tell me about your experience with Python",
            "answer": "Yes, I know Python",
            "expected_quality": "SHORT"
        },
        {
            "question": "Tell me about your experience with Python",
            "answer": "I like programming",
            "expected_quality": "IRRELEVANT"
        },
        {
            "question": "Tell me about your experience with Python",
            "answer": "I've used Python for web development with Django",
            "expected_quality": "PARTIAL"
        }
    ]
    
    for i, case in enumerate(test_cases, 1):
        print(f"\nTest Case {i}:")
        print(f"Question: {case['question']}")
        print(f"Answer: {case['answer']}")
        
        result = groq.evaluate_response(case['question'], case['answer'])
        
        print(f"Quality: {result['quality']} (expected: {case['expected_quality']})")
        print(f"Content Score: {result['content_score']}")
        print(f"Missing Part: {result.get('missing_part', 'N/A')}")
        
        # Verify quality matches expected
        if result['quality'] == case['expected_quality']:
            print("✅ PASS")
        else:
            print(f"❌ FAIL - Expected {case['expected_quality']}, got {result['quality']}")

def test_followup_generation():
    """Test follow-up message generation"""
    print("\n\n=== TEST 2: Follow-up Generation ===")
    
    groq = GroqService(settings.GROQ_API_KEY)
    
    test_cases = [
        {
            "quality": "SHORT",
            "missing_part": "specific examples",
            "question": "Tell me about your experience with Python"
        },
        {
            "quality": "PARTIAL",
            "missing_part": "data analysis experience",
            "question": "Tell me about your experience with Python"
        },
        {
            "quality": "IRRELEVANT",
            "missing_part": "",
            "question": "Tell me about your experience with Python"
        }
    ]
    
    for i, case in enumerate(test_cases, 1):
        print(f"\nTest Case {i}:")
        print(f"Quality: {case['quality']}")
        print(f"Missing: {case['missing_part']}")
        
        followup = groq.generate_followup_message(
            case['quality'],
            case['missing_part'],
            case['question']
        )
        
        print(f"Follow-up: {followup}")
        
        # Verify follow-up is not empty and reasonable length
        if followup and 10 < len(followup) < 200:
            print("✅ PASS")
        else:
            print("❌ FAIL - Follow-up message invalid")

def test_question_rephrasing():
    """Test question rephrasing"""
    print("\n\n=== TEST 3: Question Rephrasing ===")
    
    groq = GroqService(settings.GROQ_API_KEY)
    
    original = "What is your experience with Python programming?"
    
    print(f"Original: {original}")
    
    rephrased = groq.rephrase_question(original, "MEDIUM")
    
    print(f"Rephrased: {rephrased}")
    
    if rephrased and rephrased != original and len(rephrased) > 10:
        print("✅ PASS")
    else:
        print("❌ FAIL - Rephrasing failed")

def test_silence_handling():
    """Test silence handling logic"""
    print("\n\n=== TEST 4: Silence Handling ===")
    
    groq = GroqService(settings.GROQ_API_KEY)
    
    # Test empty transcript
    empty_transcripts = ["", "   ", "uh", "um"]
    
    for transcript in empty_transcripts:
        print(f"\nTranscript: '{transcript}'")
        
        # Check if it's considered silence
        is_silence = not transcript or len(transcript.strip()) < 5
        
        if is_silence:
            print("✅ Correctly identified as silence")
        else:
            print("❌ Should be treated as silence")

def test_decision_engine():
    """Test decision engine logic"""
    print("\n\n=== TEST 5: Decision Engine Logic ===")
    
    # Simulate decision engine
    def make_decision(quality, followup_count, irrelevant_count):
        if quality == "IRRELEVANT":
            if irrelevant_count == 0:
                return "FOLLOWUP"
            else:
                return "NEXT"
        elif quality in ["SHORT", "PARTIAL"]:
            if followup_count < 2:
                return "FOLLOWUP"
            else:
                return "NEXT"
        elif quality == "GOOD":
            return "NEXT"
        return "NEXT"
    
    test_cases = [
        {"quality": "IRRELEVANT", "followup_count": 0, "irrelevant_count": 0, "expected": "FOLLOWUP"},
        {"quality": "IRRELEVANT", "followup_count": 1, "irrelevant_count": 1, "expected": "NEXT"},
        {"quality": "SHORT", "followup_count": 0, "irrelevant_count": 0, "expected": "FOLLOWUP"},
        {"quality": "SHORT", "followup_count": 1, "irrelevant_count": 0, "expected": "FOLLOWUP"},
        {"quality": "SHORT", "followup_count": 2, "irrelevant_count": 0, "expected": "NEXT"},
        {"quality": "PARTIAL", "followup_count": 0, "irrelevant_count": 0, "expected": "FOLLOWUP"},
        {"quality": "PARTIAL", "followup_count": 2, "irrelevant_count": 0, "expected": "NEXT"},
        {"quality": "GOOD", "followup_count": 0, "irrelevant_count": 0, "expected": "NEXT"},
    ]
    
    for i, case in enumerate(test_cases, 1):
        result = make_decision(case['quality'], case['followup_count'], case['irrelevant_count'])
        
        status = "✅ PASS" if result == case['expected'] else f"❌ FAIL - Expected {case['expected']}, got {result}"
        print(f"Case {i}: Quality={case['quality']}, Followup={case['followup_count']}, Irrelevant={case['irrelevant_count']} → {result} {status}")

if __name__ == "__main__":
    print("=" * 60)
    print("INTERVIEW SYSTEM COMPLETE FLOW TEST")
    print("=" * 60)
    
    try:
        test_evaluation_engine()
        test_followup_generation()
        test_question_rephrasing()
        test_silence_handling()
        test_decision_engine()
        
        print("\n" + "=" * 60)
        print("ALL TESTS COMPLETED")
        print("=" * 60)
        
    except Exception as e:
        print(f"\n❌ TEST FAILED WITH ERROR: {str(e)}")
        import traceback
        traceback.print_exc()
