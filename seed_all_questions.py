"""Seed script to populate sample Aptitude topics, Aptitude questions, Coding problems, and Test cases."""

from app.database.db import SessionLocal
from app.models.aptitude import AptitudeQuestion, AptitudeTopic
from app.models.coding import CodingProblem, CodingTestCase
from sqlalchemy import func, text
from sqlalchemy.orm import Session


TECHNICAL_APTITUDE_QUESTIONS = (
    {
        "topic": "Operating Systems",
        "question_text": "Which component selects the next ready process to run on a CPU?",
        "options": ("CPU scheduler", "File system", "Device driver", "Linker"),
        "correct_option": "A",
    },
    {
        "topic": "Computer Networks",
        "question_text": "Which transport protocol provides reliable, ordered byte-stream delivery?",
        "options": ("TCP", "UDP", "ARP", "ICMP"),
        "correct_option": "A",
    },
    {
        "topic": "Object-Oriented Programming",
        "question_text": "Which principle hides an object's internal state behind a public interface?",
        "options": ("Encapsulation", "Inheritance", "Overloading", "Recursion"),
        "correct_option": "A",
    },
    {
        "topic": "Database Management Systems",
        "question_text": "Which SQL statement retrieves rows from a table?",
        "options": ("SELECT", "UPDATE", "ALTER", "DROP"),
        "correct_option": "A",
    },
    {
        "topic": "Data Structures",
        "question_text": "Which data structure processes items in first-in, first-out order?",
        "options": ("Queue", "Stack", "Heap", "Tree"),
        "correct_option": "A",
    },
)


def seed_technical_aptitude_questions(db: Session) -> None:
    """Add the canonical technical topics required by the aptitude selector."""
    topics = {}
    next_topic_id = db.query(func.max(AptitudeTopic.id)).scalar() or 0
    for seed in TECHNICAL_APTITUDE_QUESTIONS:
        topic = db.query(AptitudeTopic).filter(AptitudeTopic.name == seed["topic"]).first()
        if topic is None:
            next_topic_id += 1
            topic = AptitudeTopic(id=next_topic_id, name=seed["topic"])
            db.add(topic)
            db.flush()
        topics[seed["topic"]] = topic

    next_question_id = db.query(func.max(AptitudeQuestion.id)).scalar() or 0
    for seed in TECHNICAL_APTITUDE_QUESTIONS:
        existing = (
            db.query(AptitudeQuestion)
            .filter(AptitudeQuestion.question_text == seed["question_text"])
            .first()
        )
        if existing is not None:
            continue
        options = seed["options"]
        next_question_id += 1
        db.add(
            AptitudeQuestion(
                id=next_question_id,
                question_text=seed["question_text"],
                option_a=options[0],
                option_b=options[1],
                option_c=options[2],
                option_d=options[3],
                correct_option=seed["correct_option"],
                difficulty="medium",
                topic_id=topics[seed["topic"]].id,
                is_active=True,
            )
        )
    db.commit()
    if db.bind.dialect.name == "postgresql":
        db.execute(
            text(
                "SELECT setval(pg_get_serial_sequence('aptitude_topics', 'id'), "
                "(SELECT MAX(id) FROM aptitude_topics))"
            )
        )
        db.execute(
            text(
                "SELECT setval(pg_get_serial_sequence('aptitude_questions', 'id'), "
                "(SELECT MAX(id) FROM aptitude_questions))"
            )
        )
        db.commit()

def seed_database():
    db = SessionLocal()
    try:
        # 1. Seed Aptitude Topics
        topics_data = ["Quantitative Aptitude", "Logical Reasoning", "Verbal Ability"]
        topics = {}
        for topic_name in topics_data:
            existing = db.query(AptitudeTopic).filter(AptitudeTopic.name == topic_name).first()
            if not existing:
                existing = AptitudeTopic(name=topic_name)
                db.add(existing)
                db.flush()
            topics[topic_name] = existing.id

        # 2. Seed Aptitude Questions
        aptitude_questions = [
            # Quantitative Aptitude - Easy
            {
                "question_text": "What is the next number in the sequence: 2, 4, 8, 16, ...?",
                "option_a": "24",
                "option_b": "32",
                "option_c": "64",
                "option_d": "128",
                "correct_option": "B",
                "difficulty": "easy",
                "topic_id": topics["Quantitative Aptitude"]
            },
            {
                "question_text": "A train running at a speed of 60 km/hr crosses a pole in 9 seconds. What is the length of the train?",
                "option_a": "120 meters",
                "option_b": "150 meters",
                "option_c": "180 meters",
                "option_d": "324 meters",
                "correct_option": "B",
                "difficulty": "easy",
                "topic_id": topics["Quantitative Aptitude"]
            },
            {
                "question_text": "What is 15% of 200?",
                "option_a": "20",
                "option_b": "25",
                "option_c": "30",
                "option_d": "35",
                "correct_option": "C",
                "difficulty": "easy",
                "topic_id": topics["Quantitative Aptitude"]
            },
            # Quantitative Aptitude - Medium
            {
                "question_text": "A sum of money at simple interest amounts to $815 in 3 years and to $854 in 4 years. The sum is:",
                "option_a": "$650",
                "option_b": "$690",
                "option_c": "$698",
                "option_d": "$700",
                "correct_option": "C",
                "difficulty": "medium",
                "topic_id": topics["Quantitative Aptitude"]
            },
            {
                "question_text": "A vendor bought toffees at 6 for a rupee. How many for a rupee must he sell to gain 20%?",
                "option_a": "3",
                "option_b": "4",
                "option_c": "5",
                "option_d": "6",
                "correct_option": "C",
                "difficulty": "medium",
                "topic_id": topics["Quantitative Aptitude"]
            },
            # Quantitative Aptitude - Hard
            {
                "question_text": "Three pipes A, B and C can fill a tank in 6 hours. After working at it together for 2 hours, C is closed and A and B can fill it in 7 hours. The time taken by C alone to fill the tank is:",
                "option_a": "10 hours",
                "option_b": "12 hours",
                "option_c": "14 hours",
                "option_d": "16 hours",
                "correct_option": "C",
                "difficulty": "hard",
                "topic_id": topics["Quantitative Aptitude"]
            },
            # Logical Reasoning - Easy
            {
                "question_text": "Which word does NOT belong with the others?",
                "option_a": "Leopard",
                "option_b": "Cougar",
                "option_c": "Elephant",
                "option_d": "Lion",
                "correct_option": "C",
                "difficulty": "easy",
                "topic_id": topics["Logical Reasoning"]
            },
            {
                "question_text": "Look at this series: 7, 10, 8, 11, 9, 12, ... What number should come next?",
                "option_a": "7",
                "option_b": "10",
                "option_c": "12",
                "option_d": "13",
                "correct_option": "B",
                "difficulty": "easy",
                "topic_id": topics["Logical Reasoning"]
            },
            # Logical Reasoning - Medium
            {
                "question_text": "Pointing to a photograph of a boy Suresh said, 'He is the son of the only son of my mother.' How is Suresh related to that boy?",
                "option_a": "Brother",
                "option_b": "Uncle",
                "option_c": "Cousin",
                "option_d": "Father",
                "correct_option": "D",
                "difficulty": "medium",
                "topic_id": topics["Logical Reasoning"]
            },
            {
                "question_text": "If in a certain code, TWINKLE is written as SVHOJKD, then how would FILTERS be written in that code?",
                "option_a": "EHKSDQR",
                "option_b": "EHKSDSQ",
                "option_c": "GJMSURT",
                "option_d": "EHKSDSR",
                "correct_option": "A",
                "difficulty": "medium",
                "topic_id": topics["Logical Reasoning"]
            },
            # Logical Reasoning - Hard
            {
                "question_text": "Statements: All green are blue. All blue are white. Conclusions: I. Some green are white. II. All green are white.",
                "option_a": "Only conclusion I follows",
                "option_b": "Only conclusion II follows",
                "option_c": "Either I or II follows",
                "option_d": "Both I and II follow",
                "correct_option": "D",
                "difficulty": "hard",
                "topic_id": topics["Logical Reasoning"]
            },
            # Verbal Ability - Easy
            {
                "question_text": "Choose the synonym of the word 'BRIEF':",
                "option_a": "Limited",
                "option_b": "Small",
                "option_c": "Short",
                "option_d": "Little",
                "correct_option": "C",
                "difficulty": "easy",
                "topic_id": topics["Verbal Ability"]
            },
            # Verbal Ability - Medium
            {
                "question_text": "Choose the antonym of the word 'ENORMOUS':",
                "option_a": "Soft",
                "option_b": "Average",
                "option_c": "Tiny",
                "option_d": "Weak",
                "correct_option": "C",
                "difficulty": "medium",
                "topic_id": topics["Verbal Ability"]
            },
            # Verbal Ability - Hard
            {
                "question_text": "Find the correctly spelt word:",
                "option_a": "Entrepreneur",
                "option_b": "Entreprenur",
                "option_c": "Entrepreuner",
                "option_d": "Entreprenuer",
                "correct_option": "A",
                "difficulty": "hard",
                "topic_id": topics["Verbal Ability"]
            }
        ]

        for q_data in aptitude_questions:
            q = AptitudeQuestion(**q_data, is_active=True)
            db.add(q)

        db.flush()
        seed_technical_aptitude_questions(db)

        # 3. Seed Coding Problems & Test Cases
        coding_problems = [
            {
                "problem": {
                    "title": "Reverse a String",
                    "description": "Given a string S, return the string in reverse order.",
                    "difficulty": "easy",
                    "tags": ["string", "basics"],
                    "input_format": "A single line containing string S.",
                    "output_format": "Print the reversed string.",
                    "constraints": "1 <= length of S <= 1000"
                },
                "cases": [
                    {"input_data": "hello", "expected_output": "olleh", "is_hidden": False, "case_order": 1},
                    {"input_data": "world", "expected_output": "dlrow", "is_hidden": False, "case_order": 2},
                    {"input_data": "FastAPI", "expected_output": "IPAtsaF", "is_hidden": True, "case_order": 3}
                ]
            },
            {
                "problem": {
                    "title": "Palindrome Check",
                    "description": "Given a string S, check if it is a palindrome. Return 'true' if it is a palindrome, else return 'false'.",
                    "difficulty": "easy",
                    "tags": ["string", "two-pointer"],
                    "input_format": "A single string S.",
                    "output_format": "Print 'true' or 'false'.",
                    "constraints": "1 <= length of S <= 10^5"
                },
                "cases": [
                    {"input_data": "racecar", "expected_output": "true", "is_hidden": False, "case_order": 1},
                    {"input_data": "hello", "expected_output": "false", "is_hidden": False, "case_order": 2},
                    {"input_data": "madam", "expected_output": "true", "is_hidden": True, "case_order": 3}
                ]
            },
            {
                "problem": {
                    "title": "Find Maximum Element",
                    "description": "Given an array of N space-separated integers, output the maximum integer in the array.",
                    "difficulty": "easy",
                    "tags": ["array", "basics"],
                    "input_format": "First line contains integer N. Second line contains N space-separated integers.",
                    "output_format": "Print the maximum integer.",
                    "constraints": "1 <= N <= 10^4"
                },
                "cases": [
                    {"input_data": "5\n1 4 2 9 5", "expected_output": "9", "is_hidden": False, "case_order": 1},
                    {"input_data": "3\n-10 -5 -20", "expected_output": "-5", "is_hidden": False, "case_order": 2},
                    {"input_data": "4\n100 20 45 99", "expected_output": "100", "is_hidden": True, "case_order": 3}
                ]
            },
            {
                "problem": {
                    "title": "Two Sum",
                    "description": "Given an array of integers nums and an integer target, return indices of the two numbers such that they add up to target.",
                    "difficulty": "medium",
                    "tags": ["array", "hashmap"],
                    "input_format": "First line contains target. Second line contains space-separated integers.",
                    "output_format": "Print the two 0-based indices separated by a space.",
                    "constraints": "2 <= nums.length <= 10^4"
                },
                "cases": [
                    {"input_data": "9\n2 7 11 15", "expected_output": "0 1", "is_hidden": False, "case_order": 1},
                    {"input_data": "6\n3 2 4", "expected_output": "1 2", "is_hidden": False, "case_order": 2},
                    {"input_data": "6\n3 3", "expected_output": "0 1", "is_hidden": True, "case_order": 3}
                ]
            },
            {
                "problem": {
                    "title": "Valid Parentheses",
                    "description": "Given a string s containing just the characters '(', ')', '{', '}', '[' and ']', determine if the input string is valid.",
                    "difficulty": "medium",
                    "tags": ["stack", "string"],
                    "input_format": "A single string containing brackets.",
                    "output_format": "Print 'true' if valid, else 'false'.",
                    "constraints": "1 <= s.length <= 10^4"
                },
                "cases": [
                    {"input_data": "()[]{}", "expected_output": "true", "is_hidden": False, "case_order": 1},
                    {"input_data": "(]", "expected_output": "false", "is_hidden": False, "case_order": 2},
                    {"input_data": "{[]}", "expected_output": "true", "is_hidden": True, "case_order": 3}
                ]
            },
            {
                "problem": {
                    "title": "Longest Substring Without Repeating Characters",
                    "description": "Given a string s, find the length of the longest substring without repeating characters.",
                    "difficulty": "hard",
                    "tags": ["string", "sliding-window"],
                    "input_format": "A single string s.",
                    "output_format": "Print an integer representing length of longest substring.",
                    "constraints": "0 <= s.length <= 5 * 10^4"
                },
                "cases": [
                    {"input_data": "abcabcbb", "expected_output": "3", "is_hidden": False, "case_order": 1},
                    {"input_data": "bbbbb", "expected_output": "1", "is_hidden": False, "case_order": 2},
                    {"input_data": "pwwkew", "expected_output": "3", "is_hidden": True, "case_order": 3}
                ]
            }
        ]

        for p_item in coding_problems:
            prob = CodingProblem(**p_item["problem"])
            db.add(prob)
            db.flush()
            for c_item in p_item["cases"]:
                tc = CodingTestCase(problem_id=prob.id, **c_item)
                db.add(tc)

        db.commit()
        print("Successfully seeded Aptitude and Coding questions!")

    except Exception as e:
        db.rollback()
        print(f"Error seeding database: {e}")
        raise
    finally:
        db.close()

if __name__ == "__main__":
    seed_database()
