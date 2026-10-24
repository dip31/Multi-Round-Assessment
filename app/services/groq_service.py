"""
Groq AI service for interview question generation, classification, and brain responses.

Uses the Groq API (llama-3.3-70b-versatile model) with fallback responses
to ensure robustness against API failures.
"""

import hashlib
import json
import logging
import re
from typing import Any, Dict, List, Optional

from groq import Groq

logger = logging.getLogger(__name__)

# Current Groq production model (as of October 2026)
# llama-3.3-70b-versatile was retired by Groq (404 model_not_found); this key
# serves openai/gpt-oss-120b, verified compatible with json_object response_format.
GROQ_MODEL = "openai/gpt-oss-120b"


class GroqService:
    """Groq API client for interview-related operations."""

    def __init__(self, api_key: str):
        """Initialize Groq client with API key."""
        self.client = Groq(api_key=api_key)

    def generate_role_assessment_definition(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Return structured role and assessment design data (never candidate questions)."""
        rounds = context.get("rounds", [])
        company_evidence = context.get("company_evidence")
        system = (
            "You design role-specific assessment definitions. Understand the requested role; "
            "copy the requested target_role verbatim into the output role field; do not singularize, "
            "pluralize, abbreviate, or otherwise rephrase it. "
            "identify realistic responsibilities, skills, tools, competencies and assessment topics for each supplied round. "
            "Do not use a generic Software Engineer assessment. Do not add unrelated DSA/OOP/OS topics unless "
            "they are genuinely relevant to this role. Do not invent company-specific requirements: use them only "
            "when supported by provided evidence. Distinguish role-general knowledge from company-specific facts. "
            "Return an assessment definition, never candidate questions. Do not change configured rounds, counts, durations, or difficulty. "
            "Prefer clear subject/topic names usable by an assessment question bank; separate role responsibilities from assessable knowledge topics."
        )
        user = {
            "company": context["company_name"],
            "target_role": context["target_role"],
            "job_description": context.get("job_description"),
            "company_evidence": company_evidence,
            "configured_rounds": rounds,
            "required_json_shape": {
                "role": context["target_role"],
                "role_understanding": {
                    "summary": "string", "responsibilities": ["string"], "core_skills": ["string"],
                    "tools_and_technologies": ["string"], "competencies": ["string"]
                },
                "rounds": {
                    round_config["round_type"]: {
                        "topics": ["string"],
                        "topic_weights": {"each topic": "percentage; sum 100"},
                    } for round_config in rounds
                }
            },
            "constraints": [
                "Return exactly the configured round keys.",
                "Set role to the exact target_role string shown above, preserving spelling and singular/plural form.",
                "Use non-empty, distinct, role-relevant topics for every configured round.",
                "Topic weights must be positive and sum to 100 for each round.",
                "Use the company only as context, not as evidence of hiring history.",
                "Do not assume Software Engineer topics or invent company-specific facts.",
                "Return only role understanding, competencies, topics, and topic weights; application configuration is authoritative.",
                "Return at most 6 topics per round, with topic_weights keyed exactly by those topics.",
                "Return valid JSON only."
            ],
        }
        completion = self.client.chat.completions.create(
            model=GROQ_MODEL,
            messages=[{"role": "system", "content": system}, {"role": "user", "content": json.dumps(user)}],
            temperature=0.1,
            max_tokens=3000,
            response_format={"type": "json_object"},
            timeout=45.0,
        )
        raw = completion.choices[0].message.content or ""
        def reject_duplicate_keys(pairs):
            result = {}
            for key, value in pairs:
                if key in result:
                    raise ValueError(f"LLM JSON contains duplicate key: {key}")
                result[key] = value
            return result

        try:
            parsed = json.loads(raw, object_pairs_hook=reject_duplicate_keys)
        except (TypeError, ValueError, json.JSONDecodeError) as exc:
            raise ValueError("LLM returned malformed role assessment JSON") from exc
        if not isinstance(parsed, dict):
            raise ValueError("LLM role assessment must be a JSON object")
        return parsed

    # ── Question Pool Generation (UNCHANGED) ────────────────────────────

    def generate_question_pool(
        self,
        skills: List[str],
        projects: Dict[str, str],
        count: int = 12,
        interview_type: str = "technical",
        blueprint_constraints: Optional[Dict[str, Any]] = None,
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

        blueprint_difficulty = (blueprint_constraints or {}).get(
            "difficulty_distribution"
        )
        if isinstance(blueprint_difficulty, dict) and blueprint_difficulty:
            difficulty_instruction = (
                "- Follow the approved blueprint difficulty distribution exactly: "
                + json.dumps(blueprint_difficulty, ensure_ascii=True)
                + "."
            )
        else:
            difficulty_instruction = "- Distribute difficulty: 3 EASY, 5 MEDIUM, 4 HARD."

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
    {difficulty_instruction}
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
    {difficulty_instruction}
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
    {difficulty_instruction}

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

        if blueprint_constraints:
            constraint_lines = []
            company_name = blueprint_constraints.get("company_name")
            target_role = blueprint_constraints.get("target_role")
            if company_name or target_role:
                constraint_lines.append(
                    f"Company: {company_name or 'unspecified'}; target role: {target_role or 'unspecified'}."
                )
            configured_topics = blueprint_constraints.get("topics") or []
            if configured_topics:
                constraint_lines.append(
                    "The approved blueprint topics and weights are authoritative; keep "
                    "questions aligned to this distribution: "
                    + json.dumps(configured_topics, ensure_ascii=True)
                )
            configured_types = blueprint_constraints.get("question_types") or []
            if configured_types:
                constraint_lines.append(
                    "Use these supported question types where applicable: "
                    + json.dumps(configured_types, ensure_ascii=True)
                )
            if constraint_lines:
                prompt += "\n\nBLUEPRINT CONSTRAINTS:\n- " + "\n- ".join(constraint_lines)

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

    # ── Blueprint question pools (role-specific, pre-candidate) ────────────
    #
    # These methods generate ENTIRE question pools up front for an approved
    # blueprint (per blueprint + version + round). They are invoked by the TPO
    # "Generate Question Pool" flow, never during a candidate's live assessment.
    # Unlike generate_question_pool they NEVER substitute fallback content on
    # failure: any failure raises so the caller can mark the pool failed and
    # block publishing rather than serve unvalidated content.

    def generate_aptitude_question_pool(self, spec: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Generate ``spec['pool_size']`` aptitude MCQs pinned to the blueprint schedule.

        ``spec`` keys: company_name, target_role, pool_size, positions
        (list of ``{"topic", "difficulty" | None}`` scheduled in pool order).
        Returns validated-shape question dicts:
        ``{question_text, option_a..d, correct_option, difficulty, topic, explanation}``.
        """
        positions = spec.get("positions") or []
        schedule_lines = []
        for i, item in enumerate(positions, start=1):
            topic = item.get("topic")
            difficulty = item.get("difficulty")
            schedule_lines.append(
                f"{i}. topic: {topic}"
                + (f" | difficulty: {difficulty}" if difficulty else "")
            )
        schedule_block = (
            "\n".join(schedule_lines)
            if schedule_lines
            else "(no schedule provided: distribute across the role sensibly)"
        )

        system = (
            f"You are an expert assessment author creating a role-specific aptitude "
            f"question pool for the role '{spec['target_role']}' at '{spec['company_name']}'. "
            "Return only valid JSON."
        )
        prompt = f"""Create exactly {spec['pool_size']} multiple-choice aptitude questions for this placement assessment.

Follow the topic and difficulty schedule below EXACTLY — one output question per schedule line, in the same order, with exactly the scheduled topic and difficulty. Do not reorder, add, or drop any entry. Do not use unrelated generic topics.

Required schedule:
{schedule_block}

For every question include:
- question_text: the MCQ stem
- option_a, option_b, option_c, option_d: four realistic answer choices
- correct_option: exactly one of "A" | "B" | "C" | "D"
- difficulty: exactly "easy", "medium" or "hard" matching the schedule (if the schedule omits difficulty choose the best fit)
- topic: exactly the topic name from the schedule
- explanation: 1-2 sentence justification

Return JSON in exactly this shape:
{{"questions": [{{"question_text": "...", "option_a": "...", "option_b": "...", "option_c": "...", "option_d": "...", "correct_option": "A", "difficulty": "easy", "topic": "...", "explanation": "..."}}]}}"""
        try:
            completion = self.client.chat.completions.create(
                model=GROQ_MODEL,
                messages=[
                    {"role": "system", "content": system},
                    {"role": "user", "content": prompt},
                ],
                temperature=0.3,
                max_tokens=9000,
                timeout=60.0,
                response_format={"type": "json_object"},
            )
            raw = completion.choices[0].message.content or ""
        except Exception as exc:
            raise RuntimeError(f"Aptitude pool generation failed: {exc}") from exc

        payload = _safe_json(raw)
        if not isinstance(payload, dict) or not isinstance(payload.get("questions"), list):
            raise RuntimeError("Aptitude pool generation returned invalid JSON shape.")
        questions = payload["questions"]
        if len(questions) < spec["pool_size"]:
            raise RuntimeError(
                f"Aptitude pool generation returned {len(questions)} questions; "
                f"the blueprint requires at least {spec['pool_size']}."
            )
        return questions

    def generate_coding_problem_pool(self, spec: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Generate ``spec['pool_size']`` coding problems pinned to the blueprint schedule.

        Returns problem dicts:
        ``{title, description, difficulty, topic, constraints, input_format,
        output_format, test_cases: [{input_data, expected_output, is_hidden}]}``.
        """
        positions = spec.get("positions") or []
        schedule_lines = []
        for i, item in enumerate(positions, start=1):
            topic = item.get("topic")
            difficulty = item.get("difficulty")
            schedule_lines.append(
                f"{i}. topic: {topic}"
                + (f" | difficulty: {difficulty}" if difficulty else "")
            )
        schedule_block = (
            "\n".join(schedule_lines)
            if schedule_lines
            else "(no schedule provided: distribute across the role sensibly)"
        )

        system = (
            f"You are an expert coding-round author creating role-specific coding "
            f"problems for the role '{spec['target_role']}' at '{spec['company_name']}'. "
            "Return only valid JSON."
        )
        prompt = f"""Create exactly {spec['pool_size']} coding problems for this placement assessment.

Follow the topic and difficulty schedule below EXACTLY — one problem per schedule line, same order, with exactly the scheduled topic and difficulty. Do not reorder, add, or drop any entry.

Required schedule:
{schedule_block}

For every problem include:
- title: short problem name
- description: full problem statement (input/output explanation, invariants)
- difficulty: exactly "easy", "medium" or "hard" matching the schedule
- topic: exactly the topic name from the schedule
- constraints: constraints on inputs
- input_format and output_format: precise formats
- test_cases: at least 2 cases; the first must be a "visible" sample (is_hidden=false), the rest hidden (is_hidden=true). Every case needs non-empty input_data and expected_output. Never leak hidden cases in the description.

Return JSON in exactly this shape:
{{"problems": [{{"title": "...", "description": "...", "difficulty": "easy", "topic": "...", "constraints": "...", "input_format": "...", "output_format": "...", "test_cases": [{{"input_data": "...", "expected_output": "...", "is_hidden": false}}]}}]}}"""
        try:
            completion = self.client.chat.completions.create(
                model=GROQ_MODEL,
                messages=[
                    {"role": "system", "content": system},
                    {"role": "user", "content": prompt},
                ],
                temperature=0.3,
                max_tokens=9000,
                timeout=60.0,
                response_format={"type": "json_object"},
            )
            raw = completion.choices[0].message.content or ""
        except Exception as exc:
            raise RuntimeError(f"Coding problem pool generation failed: {exc}") from exc

        payload = _safe_json(raw)
        if not isinstance(payload, dict) or not isinstance(payload.get("problems"), list):
            raise RuntimeError("Coding problem pool generation returned invalid JSON shape.")
        problems = payload["problems"]
        if len(problems) < spec["pool_size"]:
            raise RuntimeError(
                f"Coding problem pool generation returned {len(problems)} problems; "
                f"the blueprint requires at least {spec['pool_size']}."
            )
        return problems

    def generate_interview_question_pool(
        self, spec: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """Generate ``spec['pool_size']`` interview questions for a blueprint round.

        ``spec`` keys: company_name, target_role, phase ("TECHNICAL"|"HR"),
        topics (list of configured topic names), difficulty_distribution (dict
        or {}), pool_size.
        Returns question dicts:
        ``{question, difficulty, topic, phase, expected_answer, evaluation_criteria}``
        (difficulty uppercase). ``role`` is added by the caller so the existing
        resume/start flow detects the role without another LLM round-trip.
        """
        topics = spec.get("topics") or []
        positions = spec.get("positions") or []
        difficulty_block = spec.get("difficulty_distribution") or {}
        difficulty_hint = (
            ", ".join(f"{difficulty}: {int(weight * 100)}%" for difficulty, weight in difficulty_block.items())
            if difficulty_block
            else "no fixed difficulty split (use your best judgment)"
        )

        if positions:
            schedule_lines = []
            for i, item in enumerate(positions, start=1):
                topic = item.get("topic")
                difficulty = item.get("difficulty")
                schedule_lines.append(
                    f"{i}. topic: {topic}"
                    + (f" | difficulty: {difficulty}" if difficulty else "")
                )
            schedule_block = "\n".join(schedule_lines)
            topic_instruction = (
                "Follow the topic schedule below EXACTLY — one question per schedule "
                "line, in the same order, with exactly the scheduled topic. Do not "
                "reorder, add, or drop any entry.\n\n"
                f"Required schedule:\n{schedule_block}"
            )
            topic_field_hint = "topic: exactly the topic name from the schedule"
        else:
            topics_block = (
                "\n".join(f"- {topic}" for topic in topics)
                if topics
                else "- (no topics configured)"
            )
            topic_instruction = f"Approved topics:\n{topics_block}"
            topic_field_hint = "topic: exactly one of the approved topic names above"

        system = (
            f"You are an expert {spec['phase'].lower()} interviewer. Build a role-specific "
            f"question pool for the role '{spec['target_role']}' at '{spec['company_name']}'. "
            "Return only valid JSON."
        )
        prompt = f"""Create exactly {spec['pool_size']} {spec['phase']} interview questions for this placement assessment.

The questions must be concrete, role-specific behavioral/technical questions grounded in the approved topics below. Do not fall back to generic "Software Engineer" questions unrelated to these topics or to the role.

{topic_instruction}

Difficulty split:
{difficulty_hint}

For every question include:
- question: the question text (what a human interviewer would ask)
- difficulty: exactly one of "EASY" | "MEDIUM" | "HARD"
- {topic_field_hint}
- phase: exactly "{spec['phase']}"
- expected_answer: a non-empty bullet summary of what a strong answer covers
- evaluation_criteria: 1-2 short sentences describing how to grade it

Return JSON in exactly this shape:
{{"questions": [{{"question": "...", "difficulty": "MEDIUM", "topic": "...", "phase": "{spec['phase']}", "expected_answer": "...", "evaluation_criteria": "..."}}]}}"""
        try:
            completion = self.client.chat.completions.create(
                model=GROQ_MODEL,
                messages=[
                    {"role": "system", "content": system},
                    {"role": "user", "content": prompt},
                ],
                temperature=0.4,
                max_tokens=9000,
                timeout=60.0,
                response_format={"type": "json_object"},
            )
            raw = completion.choices[0].message.content or ""
        except Exception as exc:
            raise RuntimeError(f"Interview question pool generation failed: {exc}") from exc

        payload = _safe_json(raw)
        if not isinstance(payload, dict) or not isinstance(payload.get("questions"), list):
            raise RuntimeError("Interview question pool generation returned invalid JSON shape.")
        questions = payload["questions"]
        if len(questions) < spec["pool_size"]:
            raise RuntimeError(
                f"Interview question pool generation returned {len(questions)} questions; "
                f"the blueprint requires at least {spec['pool_size']}."
            )
        return questions

    # ── Competency Configuration Generation (EDI5 Enhancement) ─────────────

    def generate_competency_configuration(self, spec: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Generate role-specific competency suggestions with weights and topic associations.

        ``spec`` keys:
        - company_name: str
        - target_role: str
        - blueprint_topics: List[str]  (canonical topics from the blueprint rounds)
        - existing_competencies: List[str] | None  (names from role_understanding.competencies)
        - round_info: List[Dict]  (each with round_type, topics, question_count)

        Returns list of competency dicts:
        {"id": str, "name": str, "weight_pct": float, "topics": List[str]}
        Weights sum to exactly 100.0 after rounding. IDs are stable slugs from names.
        """
        company_name = spec.get("company_name", "")
        target_role = spec.get("target_role", "")
        blueprint_topics = spec.get("blueprint_topics") or []
        existing_competencies = spec.get("existing_competencies") or []
        round_info = spec.get("round_info") or []

        system = (
            f"You are an expert assessment designer creating competency configurations "
            f"for the role '{target_role}' at '{company_name}'. "
            "Return only valid JSON."
        )

        topic_block = (
            "\n".join(f"- {t}" for t in blueprint_topics)
            if blueprint_topics
            else "- (no topics provided)"
        )

        round_block = ""
        if round_info:
            lines = []
            for r in round_info:
                rt = r.get("round_type", "unknown")
                topics = r.get("topics", [])
                qc = r.get("question_count", 0)
                topic_str = ", ".join(topics) if topics else "(none)"
                lines.append(f"- {rt}: {topic_str} ({qc} questions)")
            round_block = "Blueprint rounds:\n" + "\n".join(lines) + "\n\n"
        else:
            round_block = ""

        existing_comp_block = ""
        if existing_competencies:
            existing_comp_block = (
                "LLM role understanding suggested these competency names (use as inspiration, not mandatory):\n"
                + "\n".join(f"- {c}" for c in existing_competencies)
                + "\n\n"
            )

        prompt = f"""Create a competency configuration for the role '{target_role}' at '{company_name}'.

{round_block}Available canonical topics from the approved blueprint:
{topic_block}

{existing_comp_block}Requirements:
- Generate 3-6 competencies relevant to this role.
- Each competency must have a name, a weight (positive number), and 1-3 associated canonical topics from the list above.
- Competency weights must sum to exactly 100.
- Competency names must be unique and descriptive (e.g., "Product Strategy", "Analytical Reasoning", "Stakeholder Management").
- Stable IDs should be lowercase slugs derived from names (e.g., "product_strategy").
- Every associated topic must exactly match a canonical topic from the blueprint list.
- Do not invent topics not in the blueprint.
- Do not create competencies without topic associations.
- Return ONLY valid JSON, no markdown, no explanation.

Return JSON in exactly this shape:
{{"competencies": [
  {{"id": "product_strategy", "name": "Product Strategy", "weight_pct": 30.0, "topics": ["Product Management", "Business Analysis"]}},
  {{"id": "analytical_reasoning", "name": "Analytical Reasoning", "weight_pct": 25.0, "topics": ["Data Analysis", "Statistics"]}}
]}}"""

        try:
            completion = self.client.chat.completions.create(
                model=GROQ_MODEL,
                messages=[
                    {"role": "system", "content": system},
                    {"role": "user", "content": prompt},
                ],
                temperature=0.2,
                max_tokens=2000,
                timeout=45.0,
                response_format={"type": "json_object"},
            )
            raw = completion.choices[0].message.content or ""
        except Exception as exc:
            raise RuntimeError(f"Competency configuration generation failed: {exc}") from exc

        payload = _safe_json(raw)
        if not isinstance(payload, dict) or not isinstance(payload.get("competencies"), list):
            raise RuntimeError("Competency configuration generation returned invalid JSON shape.")

        competencies = payload["competencies"]
        if not competencies:
            raise RuntimeError("Competency configuration generation returned empty list.")

        # Validate and normalize
        validated = self._validate_competency_output(competencies, blueprint_topics)
        return validated

    def _validate_competency_output(self, competencies: List[Dict], blueprint_topics: List[str]) -> List[Dict[str, Any]]:
        """Validate and normalize LLM competency output to match schema requirements."""
        if not isinstance(competencies, list):
            raise RuntimeError("Competencies must be a list.")

        blueprint_topic_set = {t.strip().casefold() for t in blueprint_topics}
        seen_names = set()
        seen_ids = set()
        validated = []

        for idx, comp in enumerate(competencies):
            if not isinstance(comp, dict):
                raise RuntimeError(f"Competency {idx} must be an object.")

            # Name
            name = str(comp.get("name", "")).strip()
            if not name:
                raise RuntimeError(f"Competency {idx} missing name.")
            if name.casefold() in seen_names:
                raise RuntimeError(f"Duplicate competency name: {name}")
            seen_names.add(name.casefold())

            # ID - generate from name if not provided or invalid
            comp_id = comp.get("id")
            if comp_id:
                comp_id = str(comp_id).strip().lower().replace(" ", "_").replace("-", "_")
                comp_id = "".join(c for c in comp_id if c.isalnum() or c == "_")
            if not comp_id:
                comp_id = name.lower().replace(" ", "_").replace("-", "_")
                comp_id = "".join(c for c in comp_id if c.isalnum() or c == "_")
            comp_id = comp_id[:80]
            if comp_id.casefold() in seen_ids:
                # Make unique by appending index
                base = comp_id
                counter = 2
                while comp_id.casefold() in seen_ids:
                    comp_id = f"{base}_{counter}"
                    counter += 1
            seen_ids.add(comp_id.casefold())

            # Weight
            try:
                weight = float(comp.get("weight_pct", 0))
            except (TypeError, ValueError):
                raise RuntimeError(f"Competency '{name}' has invalid weight_pct.")
            if weight <= 0 or weight > 100:
                raise RuntimeError(f"Competency '{name}' weight_pct must be positive and <= 100.")

            # Topics
            topics = comp.get("topics")
            if not isinstance(topics, list) or not topics:
                raise RuntimeError(f"Competency '{name}' must have at least one topic.")
            norm_topics = []
            for t in topics:
                t_str = str(t).strip()
                if not t_str:
                    raise RuntimeError(f"Competency '{name}' has blank topic.")
                if t_str.casefold() not in blueprint_topic_set:
                    raise RuntimeError(f"Competency '{name}' topic '{t_str}' not in blueprint canonical topics.")
                if t_str.casefold() in {x.casefold() for x in norm_topics}:
                    raise RuntimeError(f"Competency '{name}' has duplicate topic '{t_str}'.")
                norm_topics.append(t_str)

            validated.append({
                "id": comp_id,
                "name": name,
                "weight_pct": round(weight, 2),
                "topics": norm_topics,
            })

        # Normalize weights to sum to exactly 100
        total = sum(c["weight_pct"] for c in validated)
        if total <= 0:
            raise RuntimeError("Total competency weight must be positive.")

        for c in validated:
            c["weight_pct"] = round(c["weight_pct"] * 100.0 / total, 2)

        # Fix rounding drift on the largest weight
        drift = round(100.0 - sum(c["weight_pct"] for c in validated), 2)
        if abs(drift) > 0.01:
            largest = max(validated, key=lambda c: c["weight_pct"])
            largest["weight_pct"] = round(largest["weight_pct"] + drift, 2)

        return validated


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


def _balanced_span(text: str, start: int) -> Optional[str]:
    """Return the balanced object/array substring starting at ``start``.

    Brace/bracket depth is tracked with string/escape awareness so prose around
    (and inside) the payload never widens the span. ``None`` means unbalanced.
    """
    if start >= len(text) or text[start] not in "{[":
        return None
    depth = 0
    in_string = False
    escaped = False
    for index in range(start, len(text)):
        char = text[index]
        if in_string:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                in_string = False
            continue
        if char == '"':
            in_string = True
        elif char in "{[":
            depth += 1
        elif char in "}]":
            depth -= 1
            if depth == 0:
                return text[start:index + 1]
            if depth < 0:
                return None
    return None


def _extract_json_value(text: str) -> Optional[Any]:
    """Return the first value that parses as JSON inside ``text``, or ``None``.

    Used only when the whole response is not parseable JSON (the model wrapped
    the payload in prose, possibly after a non-JSON bracket). Every candidate
    must be a complete balanced JSON value - surrounding prose is never
    returned.
    """
    attempts = 0
    for start, char in enumerate(text):
        if char not in "{[":
            continue
        attempts += 1
        if attempts > 20:
            break
        span = _balanced_span(text, start)
        if span is None:
            continue
        try:
            return json.loads(span)
        except json.JSONDecodeError:
            continue
    return None


def _safe_json(raw: str) -> dict or None:
    """
    Safely parse JSON from raw text, stripping markdown code fences.

    If the response is prose wrapped around a JSON payload, only a balanced
    JSON value is extracted and parsed; the prose itself is never returned (a
    non-JSON response always yields ``None``).
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
        pass

    extracted = _extract_json_value(cleaned)
    if extracted is not None:
        return extracted

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
