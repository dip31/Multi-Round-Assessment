#!/usr/bin/env python3
"""
Insert Divesh Rahul Lokhande's data across all recruitment stages
"""
import sqlite3
from datetime import datetime
import json

DB_PATH = "data/recruitment.db"

def insert_divesh_data():
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    
    try:
        # Get the Web Developer job ID
        cur.execute("SELECT id FROM jobs WHERE title = 'Web Developer' LIMIT 1")
        job_result = cur.fetchone()
        if not job_result:
            print("❌ Web Developer job not found. Please create it first.")
            return
        job_id = job_result[0]
        print(f"✅ Found Web Developer job with ID: {job_id}")
        
        # Check if Divesh already exists as a candidate
        cur.execute("SELECT id FROM candidates WHERE name = 'Divesh Rahul Lokhande' LIMIT 1")
        candidate_result = cur.fetchone()
        
        if candidate_result:
            candidate_id = candidate_result[0]
            print(f"✅ Found existing candidate Divesh with ID: {candidate_id}")
        else:
            # Insert Divesh as a candidate
            cur.execute("""
                INSERT INTO candidates (name, email, phone, location, experience_years, skills, source, status, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                "Divesh Rahul Lokhande",
                "diveshlokhande72@gmail.com",
                "+91-9876543210",
                "Mumbai, India",
                3,
                json.dumps(["JavaScript", "React", "Node.js", "HTML", "CSS"]),
                "uploaded",
                "active",
                datetime.now().isoformat()
            ))
            candidate_id = cur.lastrowid
            print(f"✅ Created candidate Divesh with ID: {candidate_id}")
        
        # Stage 3: Insert application with screening results
        cur.execute("SELECT id FROM applications WHERE candidate_id = ? AND job_id = ?", (candidate_id, job_id))
        if not cur.fetchone():
            cur.execute("""
                INSERT INTO applications (candidate_id, job_id, status, score, rejection_reason, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (
                candidate_id,
                job_id,
                "shortlisted",
                0.88,
                None,
                datetime.now().isoformat()
            ))
            print("✅ Stage 3: Added screening results - shortlisted with 0.88 score")
        else:
            cur.execute("""
                UPDATE applications 
                SET status = 'shortlisted', score = 0.88
                WHERE candidate_id = ? AND job_id = ?
            """, (candidate_id, job_id))
            print("✅ Stage 3: Updated screening results - shortlisted with 0.88 score")
        
        # Stage 4: Insert outreach communication
        cur.execute("SELECT id FROM communications WHERE candidate_id = ? AND job_id = ?", (candidate_id, job_id))
        if not cur.fetchone():
            cur.execute("""
                INSERT INTO communications (candidate_id, job_id, email, outreach_sent, status, actions, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                candidate_id,
                job_id,
                "diveshlokhande72@gmail.com",
                "yes",
                "sent",
                "forwarded",
                datetime.now().isoformat()
            ))
            print("✅ Stage 4: Added outreach communication - sent and forwarded")
        else:
            cur.execute("""
                UPDATE communications 
                SET email = 'diveshlokhande72@gmail.com', outreach_sent = 'yes', status = 'sent', actions = 'forwarded'
                WHERE candidate_id = ? AND job_id = ?
            """, (candidate_id, job_id))
            print("✅ Stage 4: Updated outreach communication - sent and forwarded")
        
        # Stage 5: Insert prescreening session
        cur.execute("SELECT id FROM chatbot_sessions WHERE candidate_id = ?", (candidate_id,))
        if not cur.fetchone():
            cur.execute("""
                INSERT INTO chatbot_sessions (candidate_id, job_id, session_status, questions_answered, actions, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (
                candidate_id,
                job_id,
                "done",
                6,
                "done",
                datetime.now().isoformat()
            ))
            print("✅ Stage 5: Added prescreening session - 6 questions answered, status done")
        else:
            cur.execute("""
                UPDATE chatbot_sessions 
                SET session_status = 'done', questions_answered = 6, actions = 'done'
                WHERE candidate_id = ?
            """, (candidate_id,))
            print("✅ Stage 5: Updated prescreening session - 6 questions answered, status done")
        
        # Stage 6 & 7: Insert interview session
        cur.execute("SELECT id FROM interview_sessions WHERE candidate_id = ?", (candidate_id,))
        interview_result = cur.fetchone()
        
        if not interview_result:
            cur.execute("""
                INSERT INTO interview_sessions (
                    candidate_id, overall_score, content_score, behavior_score, 
                    phase, total_turns, feedback_summary, turn_reviews, recommendation, created_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                candidate_id,
                0.9,
                0.85,
                0.95,
                "COMPLETE",
                8,
                "Excellent candidate with strong technical skills and good communication. Demonstrated solid understanding of web development concepts and showed enthusiasm for the role.",
                json.dumps([
                    {"turn": 1, "score": 0.8, "feedback": "Good introduction and background"},
                    {"turn": 2, "score": 0.9, "feedback": "Strong technical knowledge in JavaScript"},
                    {"turn": 3, "score": 0.85, "feedback": "Good problem-solving approach"},
                    {"turn": 4, "score": 0.9, "feedback": "Excellent React knowledge"},
                    {"turn": 5, "score": 0.95, "feedback": "Great communication skills"},
                    {"turn": 6, "score": 0.9, "feedback": "Good questions about the role"},
                    {"turn": 7, "score": 0.85, "feedback": "Solid understanding of best practices"},
                    {"turn": 8, "score": 0.9, "feedback": "Strong closing and enthusiasm"}
                ]),
                "hire",
                datetime.now().isoformat()
            ))
            interview_id = cur.lastrowid
            print(f"✅ Stage 6 & 7: Added interview results - ID: {interview_id}, overall score: 0.9, recommendation: hire")
        else:
            interview_id = interview_result[0]
            cur.execute("""
                UPDATE interview_sessions 
                SET overall_score = 0.9, content_score = 0.85, behavior_score = 0.95,
                    phase = 'COMPLETE', total_turns = 8, 
                    feedback_summary = 'Excellent candidate with strong technical skills and good communication. Demonstrated solid understanding of web development concepts and showed enthusiasm for the role.',
                    turn_reviews = ?, recommendation = 'hire'
                WHERE candidate_id = ?
            """, (
                json.dumps([
                    {"turn": 1, "score": 0.8, "feedback": "Good introduction and background"},
                    {"turn": 2, "score": 0.9, "feedback": "Strong technical knowledge in JavaScript"},
                    {"turn": 3, "score": 0.85, "feedback": "Good problem-solving approach"},
                    {"turn": 4, "score": 0.9, "feedback": "Excellent React knowledge"},
                    {"turn": 5, "score": 0.95, "feedback": "Great communication skills"},
                    {"turn": 6, "score": 0.9, "feedback": "Good questions about the role"},
                    {"turn": 7, "score": 0.85, "feedback": "Solid understanding of best practices"},
                    {"turn": 8, "score": 0.9, "feedback": "Strong closing and enthusiasm"}
                ]),
                candidate_id
            ))
            print(f"✅ Stage 6 & 7: Updated interview results - ID: {interview_id}, overall score: 0.9, recommendation: hire")
        
        # Commit all changes
        conn.commit()
        print("\n🎉 Successfully inserted Divesh Rahul Lokhande's data across all stages!")
        print(f"📊 Summary:")
        print(f"   - Candidate ID: {candidate_id}")
        print(f"   - Job ID: {job_id} (Web Developer)")
        print(f"   - Stage 3: Shortlisted with 0.88 score")
        print(f"   - Stage 4: Outreach sent and forwarded")
        print(f"   - Stage 5: Prescreening completed (6 questions)")
        print(f"   - Stage 6 & 7: Interview completed with 0.9 score, recommended for hire")
        
    except Exception as e:
        conn.rollback()
        print(f"❌ Error inserting data: {e}")
        raise
    finally:
        conn.close()

if __name__ == "__main__":
    insert_divesh_data()