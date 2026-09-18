"""
Groq AI service for interview question generation, classification, and brain responses.

Uses the Groq API (llama-3.3-70b-versatile model) with fallback responses
to ensure robustness against API failures.
"""

import hashlib
import json
import logging
import re
from typing import Dict, List, Optional

from groq import Groq

logger = logging.getLogger(__name__)

# Current Groq production model (as of March 2026)
GROQ_MODEL = "llama-3.3-70b-versatile"


class GroqService:
    """Groq API client for interview-related operations."""

    def __init__(self, api_key: str):
        """Initialize Groq client with API key."""
        self.client = Groq(api_key=api_key)

    # ── Question Pool Generation (UNCHANGED) ────────────────────────────

    def generate_question_pool(
        self,
        skills: List[str],
        projects: Dict[str, str],
        count: int = 12,
        interview_type: str = "technical",
    ) -> List[Dict]:
        """
        Generate personalized interview question pool using Groq.

        Questions are grounded in the candidate's extracted skills and projects,
        and strictly aligned to the interview type ('technical', 'hr', or 'communication').
        """
        from app.services.role_detection_service import detect_role
        from app.services.retriever_service import (
            retrieve, format_for_prompt
        )

        norm_type = (interview_type or "technical").lower().strip()
        if norm_type not in ("technical", "hr", "communication"):
            norm_type = "technical"

        # Step 1: Detect role
        detected_role = detect_role(skills, projects)

        # Step 2: Retrieve relevant knowledge (relevant for technical, general background for others)
        try:
            retrieved_docs = retrieve(
                skills=skills,
                projects=projects,
                detected_role=detected_role,
                k=8,
                final_k=5
            )
            context = format_for_prompt(retrieved_docs)
        except Exception as e:
            print(f"[RAG] Retrieval failed: {e}")
            context = "No additional context available."
            retrieved_docs = []

        # Step 3: Build grounded prompt based on interview type
        if norm_type == "technical":
            prompt = f"""
      You are an expert technical interviewer conducting a campus placement technical interview.

      CANDIDATE PROFILE:
      Technical Skills: {skills}
      Projects: {projects}
      Target Role: {detected_role}

      RETRIEVED KNOWLEDGE BASE:
      {context}

      INSTRUCTIONS:
      - Generate exactly {count} TECHNICAL interview questions.
      - Every question MUST be a technical question focusing on:
        1. Programming languages and problem solving
        2. Data Structures and Algorithms
        3. CS fundamentals (OOPS, DBMS, Operating Systems, Computer Networks)
        4. Technical architecture and implementation details of candidate's projects ({projects})
        5. Deep-dive into technical skills ({skills})
      - ALL questions must have "phase": "TECHNICAL".
      - Distribute difficulty: 3 EASY, 5 MEDIUM, 4 HARD.
      - Make questions personalized to candidate's projects and skills where possible.

      Return ONLY valid JSON, no markdown:
      {{
        "detected_role": "{detected_role}",
        "questions": [
          {{
            "question": "...",
            "difficulty": "EASY|MEDIUM|HARD",
            "topic": "...",
            "phase": "TECHNICAL",
            "grounded_in": "which skill or project inspired this",
            "personalized": true
          }}
        ]
      }}
      """
        elif norm_type == "hr":
            prompt = f"""
      You are an expert HR director conducting a behavioral and HR placement interview.

      CANDIDATE PROFILE:
      Background / Skills: {skills}
      Projects: {projects}
      Target Role: {detected_role}

      INSTRUCTIONS:
      - Generate exactly {count} HR and BEHAVIORAL interview questions.
      - Focus on:
        1. Professional introduction and career motivations
        2. Key strengths, areas for growth, and continuous learning
        3. Team collaboration, leadership, and conflict resolution
        4. Handling failure, pressure, and unexpected setbacks
        5. Situational workplace judgment (STAR method: Situation, Task, Action, Result)
        6. Alignment with company values and long-term goals
      - ALL questions must have "phase": "HR".
      - Distribute difficulty: 3 EASY, 5 MEDIUM, 4 HARD.
      - Vary the questions so they feel human, authentic, and situational.

      Return ONLY valid JSON, no markdown:
      {{
        "detected_role": "{detected_role}",
        "questions": [
          {{
            "question": "...",
            "difficulty": "EASY|MEDIUM|HARD",
            "topic": "...",
            "phase": "HR",
            "grounded_in": "behavioral competency",
            "personalized": true
          }}
        ]
      }}
      """
        else:  # communication
            prompt = f"""
      You are an expert executive communication coach evaluating candidate communication and articulation.

      CANDIDATE PROFILE:
      Background / Skills: {skills}
      Projects: {projects}
      Target Role: {detected_role}

      INSTRUCTIONS:
      - Generate exactly {count} COMMUNICATION-focused interview questions.
      - Focus on:
        1. Structured professional self-introduction
        2. Explaining a complex technical concept simply to a non-technical stakeholder
        3. Pitching or narrating a key project with clarity and business context
        4. Handling a workplace communication breakdown or persuasion scenario
        5. Explaining their problem-solving thought process step-by-step
        6. Delivering constructive feedback or presenting a structured opinion
      - ALL questions must have "phase": "COMMUNICATION".
      - Distribute difficulty: 3 EASY, 5 MEDIUM, 4 HARD.

      Return ONLY valid JSON, no markdown:
      {{
        "detected_role": "{detected_role}",
        "questions": [
          {{
            "question": "...",
            "difficulty": "EASY|MEDIUM|HARD",
            "topic": "...",
            "phase": "COMMUNICATION",
            "grounded_in": "communication scenario",
            "personalized": true
          }}
        ]
      }}
      """

        try:
            result = _safe_json(
                self.client.chat.completions.create(
                    model=GROQ_MODEL,
                    messages=[{
                        "role": "user",
                        "content": prompt
                    }],
                    temperature=0.3,
                    max_tokens=2000
                ).choices[0].message.content
            )
        except Exception as e:
            print(f"[RAG] Groq call failed: {e}")
            result = None

        if result and "questions" in result:
            questions = result["questions"]
            for idx, q in enumerate(questions, 1):
                q["role"] = detected_role
                q["id"] = hashlib.md5(q["question"].encode()).hexdigest()[:12]
            return questions

        # Fallback question banks strictly tailored to the requested interview type
        print(f"[RAG] Using fallback questions for {norm_type} interview")
        fallback = []
        if norm_type == "technical":
            tech_fallbacks = [
                ("Explain the lifecycle of a request in your recent project and where data persistence happens.", "MEDIUM", "Projects"),
                ("How would you optimize database queries when dealing with millions of records?", "HARD", "DBMS"),
                ("What is the difference between processes and threads, and how does inter-process communication work?", "MEDIUM", "OS"),
                ("Explain the ACID properties in database transactions and why each is necessary.", "EASY", "DBMS"),
                ("What are the core pillars of Object-Oriented Programming, and how does polymorphism differ at compile-time vs runtime?", "EASY", "OOPS"),
                ("Explain how a Hash Map operates internally, including collision handling techniques.", "MEDIUM", "DSA"),
                ("What happens at the network layer during the TCP three-way handshake?", "MEDIUM", "Networks"),
                ("How would you design a scalable cache system using Redis or Memcached?", "HARD", "System Design"),
                ("Explain the time and space complexity tradeoffs between QuickSort and MergeSort.", "EASY", "DSA"),
                ("How does virtual memory and demand paging prevent processes from corrupting each other's memory space?", "HARD", "OS"),
                ("Describe an interesting bug you resolved in your code and your systematic debugging process.", "MEDIUM", "Problem Solving"),
                ("What are microservices compared to monolithic architecture, and what challenges arise with distributed transactions?", "HARD", "Architecture"),
            ]
            for idx, (q_txt, diff, top) in enumerate(tech_fallbacks[:count], 1):
                fallback.append({
                    "id": hashlib.md5(q_txt.encode()).hexdigest()[:12],
                    "question": q_txt,
                    "difficulty": diff,
                    "topic": top,
                    "phase": "TECHNICAL",
                    "grounded_in": "technical fallback",
                    "personalized": False,
                    "role": detected_role,
                })
        elif norm_type == "hr":
            hr_fallbacks = [
                ("Walk me through your background and what motivated you to pursue a career in technology.", "EASY", "Introduction"),
                ("Tell me about a time you faced a difficult conflict with a team member and how you resolved it.", "MEDIUM", "Conflict Resolution"),
                ("What do you consider your greatest professional strength and one area you are actively improving?", "EASY", "Self Awareness"),
                ("Describe a project that failed or did not go according to plan. What did you learn from it?", "MEDIUM", "Resilience"),
                ("Where do you envision yourself professionally in three to five years?", "EASY", "Career Goals"),
                ("Tell me about a situation where you had to work under tight deadlines with ambiguous requirements.", "HARD", "Adaptability"),
                ("How do you handle receiving critical feedback from a peer or manager?", "MEDIUM", "Feedback"),
                ("Describe a time you took initiative to lead a project or solve an unassigned problem.", "HARD", "Leadership"),
                ("What factors are most important to you when evaluating a company's culture and work environment?", "EASY", "Culture Fit"),
                ("Tell me about a time you had to persuade someone who initially disagreed with your proposal.", "HARD", "Persuasion"),
                ("How do you prioritize competing tasks when everything feels urgent?", "MEDIUM", "Time Management"),
                ("Why do you want to join our institution's placement drives and work in this domain?", "EASY", "Motivation"),
            ]
            for idx, (q_txt, diff, top) in enumerate(hr_fallbacks[:count], 1):
                fallback.append({
                    "id": hashlib.md5(q_txt.encode()).hexdigest()[:12],
                    "question": q_txt,
                    "difficulty": diff,
                    "topic": top,
                    "phase": "HR",
                    "grounded_in": "hr fallback",
                    "personalized": False,
                    "role": detected_role,
                })
        else:  # communication
            comm_fallbacks = [
                ("Please introduce yourself and highlight the central theme of your engineering journey in under two minutes.", "EASY", "Self Introduction"),
                ("Explain the concept of an API or database indexing as if you were explaining it to a non-technical business executive.", "MEDIUM", "Simplification"),
                ("Tell the story of a project you built: the problem, your architectural choices, and the measurable outcome.", "MEDIUM", "Project Storytelling"),
                ("Describe a scenario where a client or teammate misunderstood your message. How did you realign expectations?", "HARD", "Clarity & Conflict"),
                ("Take a stand on whether remote work improves or hampers software engineering productivity, and give two structured supporting arguments.", "MEDIUM", "Structured Opinion"),
                ("How do you prepare and structure a technical presentation when delivering it to senior stakeholders?", "HARD", "Executive Presence"),
                ("Explain how you explain technical debt to a product manager who wants new features delivered immediately.", "HARD", "Stakeholder Communication"),
                ("What strategies do you use to ensure active listening during high-stakes technical meetings?", "EASY", "Active Listening"),
                ("Summarize the most complex technical paper, article, or documentation you read recently into three key takeaways.", "MEDIUM", "Synthesis"),
                ("If you noticed an error in a senior engineer's code during a code review, how would you phrase your comment constructively?", "MEDIUM", "Diplomacy"),
                ("Describe how you structure written documentation so that a new developer can onboard smoothly.", "EASY", "Documentation"),
                ("Explain your step-by-step thought process for estimating how long a challenging software feature will take to deliver.", "HARD", "Process Articulation"),
            ]
            for idx, (q_txt, diff, top) in enumerate(comm_fallbacks[:count], 1):
                fallback.append({
                    "id": hashlib.md5(q_txt.encode()).hexdigest()[:12],
                    "question": q_txt,
                    "difficulty": diff,
                    "topic": top,
                    "phase": "COMMUNICATION",
                    "grounded_in": "communication fallback",
                    "personalized": False,
                    "role": detected_role,
                })

        return fallback[:count]

    # ── Question Rephrasing (UNCHANGED) ──────────────────────────────────

    def rephrase_question(self, question: str, difficulty: str) -> str:
        """Rephrase a question naturally for the given difficulty level."""
        prompt = f"""Rephrase this interview question naturally and conversationally for a {difficulty} level candidate. 
Make it sound like a human interviewer is asking it. Return only the rephrased question, nothing else:

{question}"""

        try:
            completion = self.client.chat.completions.create(
                model=GROQ_MODEL,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.5,
                max_tokens=200,
            )
            response_text = completion.choices[0].message.content.strip()
            return response_text if response_text else question
        except Exception as e:
            logger.error(f"Groq rephrasing failed: {str(e)}, returning original question")
            return question

    # ── Classifier (NEW — spec step 2) ───────────────────────────────────

    def classify_answer(self, question: str, answer: str, interview_type: str = "technical") -> Dict:
        """
        Classify answer quality, intent, and score content.

        Deterministic — temp=0.2.
        Returns: {quality, intent, missing_part, content_score}
        """
        norm_type = (interview_type or "technical").lower().strip()
        if norm_type == "hr":
            role_desc = "You are an expert HR interviewer evaluating a candidate's response in a behavioral placement interview. Evaluate behavioral reasoning, structured response, honesty, and professional attitude."
        elif norm_type == "communication":
            role_desc = "You are an expert executive communication interviewer evaluating a candidate's response in a communication placement interview. Evaluate clarity, structure, conciseness, articulation, and relevance."
        else:
            role_desc = "You are an expert technical interviewer evaluating a candidate's response in a technical placement interview. Evaluate technical correctness, depth, problem solving, and relevance."

        prompt = f"""{role_desc}

Question: {question}
Candidate Answer: {answer}

Analyze and classify:

QUALITY — how well the answer addresses the question:
  IRRELEVANT : answer has nothing to do with the question
  SHORT      : relevant but too brief, needs elaboration
  PARTIAL    : relevant, covers some aspects but misses key parts
  GOOD       : relevant and sufficiently complete

INTENT — candidate's attitude and engagement:
  POSITIVE   : engaged, willing, enthusiastic
  NEUTRAL    : answering factually without strong stance
  NEGATIVE   : disinterested, resistant, contradictory, or explicitly stating lack of interest

Score guide for content_score:
  IRRELEVANT = 0.0 to 0.1
  SHORT      = 0.1 to 0.4
  PARTIAL    = 0.4 to 0.7
  GOOD       = 0.7 to 1.0

Return ONLY valid JSON, no markdown, no explanation:
{{
  "quality": "IRRELEVANT | SHORT | PARTIAL | GOOD",
  "intent": "POSITIVE | NEUTRAL | NEGATIVE",
  "missing_part": "specific concept missing or null if GOOD",
  "content_score": 0.0
}}"""

        try:
            completion = self.client.chat.completions.create(
                model=GROQ_MODEL,
                messages=[
                    {
                        "role": "system",
                        "content": "You are an expert interview evaluator. Return only valid JSON.",
                    },
                    {
                        "role": "user",
                        "content": prompt,
                    },
                ],
                temperature=0.2,
                max_tokens=300,
            )

            raw_response = completion.choices[0].message.content
            parsed = _safe_json(raw_response)

            if parsed and "quality" in parsed and "content_score" in parsed:
                quality = parsed.get("quality", "SHORT").strip()
                if quality not in ("IRRELEVANT", "SHORT", "PARTIAL", "GOOD"):
                    quality = "SHORT"

                intent = parsed.get("intent", "NEUTRAL").strip()
                if intent not in ("POSITIVE", "NEUTRAL", "NEGATIVE"):
                    intent = "NEUTRAL"

                return {
                    "quality": quality,
                    "intent": intent,
                    "missing_part": parsed.get("missing_part"),
                    "content_score": max(0.0, min(1.0, float(parsed.get("content_score", 0.3)))),
                }
            else:
                logger.warning("Groq classifier returned invalid JSON, using fallback")
                return _classifier_fallback()
        except Exception as e:
            logger.error(f"Groq classifier failed: {str(e)}")
            return _classifier_fallback()

    # ── Interviewer Brain (NEW — spec step 7) ────────────────────────────

    def generate_interviewer_response(
        self,
        question: str,
        answer: str,
        quality: str,
        intent: str,
        missing_part: Optional[str],
        action: str,
        followup_type: Optional[str],
        next_question: Optional[str],
        conversation_history: List[Dict],
    ) -> str:
        """
        Generate what the interviewer says next.

        Conversational — temp=0.7.
        Returns: plain string, max 2 sentences.
        """
        # Format conversation history (last 6 entries = last 3 turns)
        formatted_history = "\n".join([
            f"{'Interviewer' if e['role'] == 'interviewer' else 'Candidate'}: {e['content']}"
            for e in (conversation_history or [])
        ])

        # Build task string based on action + followup_type
        task = self._build_brain_task(action, followup_type, missing_part, next_question)

        system_prompt = f"""You are a professional interviewer conducting a campus placement interview for an engineering student.

Your personality:
- Warm but professional
- Encouraging but honest
- Direct without being harsh
- You NEVER lecture or explain the answer
- You NEVER repeat what the candidate just said back to them
- You NEVER ask two questions in one response
- Maximum 2 sentences in your response
- Sound human, not like a bot reading a script

Recent conversation history:
{formatted_history}

Current exchange:
Question you asked: {question}
Candidate's answer: {answer}
Answer quality: {quality}
Candidate intent: {intent}
Missing or notable topic: {missing_part or 'none'}
Decision: {action}

{task}

Return ONLY what you say as the interviewer.
No labels, no formatting, no quotes."""

        try:
            completion = self.client.chat.completions.create(
                model=GROQ_MODEL,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": "Generate your response as the interviewer."},
                ],
                temperature=0.7,
                max_tokens=150,
            )

            response = completion.choices[0].message.content.strip()
            return response if response else self._brain_fallback(action, followup_type, missing_part, next_question)
        except Exception as e:
            logger.error(f"Interviewer brain failed: {str(e)}")
            return self._brain_fallback(action, followup_type, missing_part, next_question)

    def _build_brain_task(self, action: str, followup_type: Optional[str],
                          missing_part: Optional[str], next_question: Optional[str]) -> str:
        """Build the task instruction string for the interviewer brain."""
        if action == "FOLLOWUP":
            if followup_type == "NEGATIVE":
                return ("The candidate expressed disinterest or resistance. "
                        "Acknowledge their honesty briefly, then professionally "
                        "challenge or redirect them. If they said they are not interested "
                        "in a topic, ask what drew them to apply or how they plan to adapt. "
                        "Be polite but firm.")
            elif followup_type == "IRRELEVANT":
                return (f"The candidate's answer was off-topic. Acknowledge briefly, "
                        f"then redirect them specifically to: {missing_part or 'the original question'}. "
                        f"Do not sound accusatory.")
            elif followup_type == "SHORT":
                return ("The candidate gave a very brief answer. Encourage them to elaborate. "
                        "Sound interested and patient.")
            elif followup_type == "PARTIAL":
                return (f"The candidate answered partially. Acknowledge what they covered, "
                        f"then guide them toward the missing part: {missing_part or 'key details'}. "
                        f"Do not give the answer.")
        elif action == "NEXT":
            return (f"The candidate has answered sufficiently. Give a brief natural transition "
                    f"in one sentence, then ask this next question: {next_question} "
                    f"The transition should feel like a real conversation, not robotic. "
                    f"Examples: 'That's clear, let's shift gears —' or 'Good, building on that —' "
                    f"or 'Alright,'")
        elif action == "COMPLETE":
            return ("The interview is now complete. Give a warm, professional closing statement. "
                    "Thank the candidate for their time. Do not reveal scores. "
                    "Wish them well. Maximum 2 sentences.")
        return ""

    def _brain_fallback(self, action: str, followup_type: Optional[str],
                        missing_part: Optional[str], next_question: Optional[str]) -> str:
        """Fallback strings if Groq fails — NEVER crash on API fail."""
        if action == "FOLLOWUP":
            fallbacks = {
                "SHORT": "Could you elaborate on that in more detail?",
                "PARTIAL": f"Good start. Can you expand on {missing_part or 'that point'}?",
                "NEGATIVE": "That's honest. How do you see yourself adapting to this?",
                "IRRELEVANT": "Let's refocus — could you address the original question?",
            }
            return fallbacks.get(followup_type, "Could you provide more details?")
        elif action == "NEXT":
            return f"Got it. {next_question or 'Let me ask you another question.'}"
        elif action == "COMPLETE":
            return "Thank you for your time today. Best of luck!"
        return "Let's continue."

    # ── Feedback Summary (UNCHANGED) ─────────────────────────────────────

    def generate_feedback_summary(self, turns_data: List[Dict]) -> str:
        """Generate a personalized feedback summary based on all interview turns."""
        prompt = f"""Based on these interview responses, write a 3-sentence personalized feedback summary for the candidate covering strengths, weaknesses, and improvement areas. Be specific and constructive.

Turns:
{json.dumps(turns_data, indent=2)}"""

        try:
            completion = self.client.chat.completions.create(
                model=GROQ_MODEL,
                messages=[
                    {
                        "role": "system",
                        "content": "You are an expert career coach providing constructive feedback.",
                    },
                    {
                        "role": "user",
                        "content": prompt,
                    },
                ],
                temperature=0.4,
                max_tokens=400,
            )

            response_text = completion.choices[0].message.content.strip()
            return response_text if response_text else "Interview completed successfully."
        except Exception as e:
            logger.error(f"Groq feedback generation failed: {str(e)}")
            return "Interview completed successfully."


# ── Speech-to-Text (NEW — spec step 2) ─────────────────────────────────

    def transcribe_audio(self, audio_file_path: str) -> str:
        """
        Transcribes audio using Groq whisper-large-v3-turbo.
        
        Model: whisper-large-v3-turbo
          → fastest Whisper on Groq
          → ~216x realtime speed
          → replaces local Whisper base model
          → fixes 503 errors caused by local model load failures
        
        Returns: transcript string (stripped)
        Returns: empty string on ANY failure — never raises
        
        The caller (/stt endpoint) handles empty string as silence.
        """
        import os
        try:
            with open(audio_file_path, "rb") as audio_file:
                transcription = self.client.audio.transcriptions.create(
                    file=(
                        os.path.basename(audio_file_path),
                        audio_file.read()
                    ),
                    model="whisper-large-v3-turbo",
                    response_format="text",
                    language="en"
                )
            return transcription.strip() if transcription else ""
        
        except Exception as e:
            print(f"[Groq STT Error] {e}")
            return ""


# ── Module-level helpers ─────────────────────────────────────────────────

def _classifier_fallback() -> Dict:
    """Fallback classifier result when Groq fails."""
    return {
        "quality": "SHORT",
        "intent": "NEUTRAL",
        "missing_part": None,
        "content_score": 0.3,
    }


def _safe_json(raw: str) -> dict or None:
    """
    Safely parse JSON from raw text, stripping markdown code fences.
    """
    cleaned = raw.strip()
    if cleaned.startswith("```json"):
        cleaned = cleaned[7:]
    if cleaned.startswith("```"):
        cleaned = cleaned[3:]
    if cleaned.endswith("```"):
        cleaned = cleaned[:-3]

    cleaned = cleaned.strip()

    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        logger.warning(f"Failed to parse JSON: {raw[:100]}...")
        return None


def _get_fallback_questions() -> List[Dict[str, str]]:
    """Return hardcoded fallback questions when Groq fails."""
    return [
        {
            "id": "fallback_1",
            "question": "Tell me about yourself and your professional background.",
            "difficulty": "EASY",
            "topic": "General",
            "phase": "HR",
        },
        {
            "id": "fallback_2",
            "question": "Describe your most challenging technical project and what you learned from it.",
            "difficulty": "MEDIUM",
            "topic": "Experience",
            "phase": "HR",
        },
    ]
