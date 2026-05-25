"""
Groq AI service for interview question generation, classification, and brain responses.

Uses the Groq API (llama-3.3-70b-versatile model) with fallback responses
to ensure robustness against API failures.
"""

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

    def generate_question_pool(self, skills: List[str], projects: Dict[str, str], count: int = 12) -> List[Dict]:
        """
        Generate personalized interview question pool using Groq.

        Questions are grounded in the candidate's extracted skills and projects.
        """
        prompt = f"""You are an expert technical interviewer. Generate {count} interview questions personalized to this candidate's background.

Candidate skills: {', '.join(skills) if skills else 'Not specified'}

Candidate projects: {json.dumps(projects, indent=2) if projects else 'No projects listed'}

Generate questions that directly reference their skills and projects. Mix HR and Technical questions.
Return ONLY valid JSON, no markdown code fences:
{{"questions": [{{"question": "...", "difficulty": "EASY|MEDIUM|HARD", "topic": "...", "phase": "HR|TECHNICAL"}}]}}"""

        try:
            completion = self.client.chat.completions.create(
                model=GROQ_MODEL,
                messages=[
                    {
                        "role": "system",
                        "content": "You are an expert technical interviewer. You generate personalized interview questions.",
                    },
                    {
                        "role": "user",
                        "content": prompt,
                    },
                ],
                temperature=0.3,
                max_tokens=2000,
            )

            raw_response = completion.choices[0].message.content
            parsed = _safe_json(raw_response)

            if parsed and "questions" in parsed:
                questions = parsed["questions"]
                for i, q in enumerate(questions):
                    if "id" not in q:
                        q["id"] = f"q_{i}_{hash(q['question']) % 10000}"
                return questions
            else:
                logger.warning("Groq returned invalid JSON format, using fallback")
                return _get_fallback_questions()
        except Exception as e:
            logger.error(f"Groq question generation failed: {str(e)}, using fallback")
            return _get_fallback_questions()

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

    def classify_answer(self, question: str, answer: str) -> Dict:
        """
        Classify answer quality, intent, and score content.

        Deterministic — temp=0.2.
        Returns: {quality, intent, missing_part, content_score}
        """
        prompt = f"""You are an expert technical interviewer evaluating a candidate's response in a campus placement interview.

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

