"""
Interviewer profiles — who the candidate appears to be talking to.

A profile is *presentation only*: a name, a face, a voice, and a speaking
style. Selecting a different interviewer changes how the interview sounds, and
nothing else.

    ┌─────────────────────────────┬──────────────────────────────────────┐
    │ A profile MAY influence     │ A profile MUST NEVER influence       │
    ├─────────────────────────────┼──────────────────────────────────────┤
    │ displayed name and avatar   │ which questions are asked            │
    │ TTS voice, pace, language   │ answer classification or scoring     │
    │ greeting wording            │ whether a follow-up is asked         │
    │ tone of the spoken line     │ difficulty selection / RL state      │
    │                             │ number of turns or interview length  │
    └─────────────────────────────┴──────────────────────────────────────┘

That boundary is why persona data lives here rather than in ``rl_state``: two
candidates who give identical answers must receive identical scores regardless
of which interviewer they picked, and a session's RL state must stay comparable
across interviewers.

Profiles are declared as data and looked up through the accessors below. There
is deliberately no ``if interviewer_id == "...":`` branching anywhere — adding
an interviewer means adding an entry to ``_PROFILES``, nothing more.

Storage is a Python dict today because the roster is small, fixed, and
changes with deploys rather than at runtime. Every consumer goes through
``get_interviewer`` / ``list_interviewers``, so swapping in a database-backed
implementation later means rewriting those two functions and nothing else.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


# ── Invariant style rules ──────────────────────────────────────────────────
# Applied to EVERY interviewer, and not overridable per profile. These are not
# stylistic preferences — they bound the interview itself. The two-sentence cap
# controls turn length and therefore total interview duration; the "never
# lecture" and "never ask two questions" rules stop the interviewer from
# feeding answers or collapsing two turns into one, which would corrupt
# scoring. A persona that could override these could change assessment
# outcomes, which is exactly what this layer must not do.
INVARIANT_STYLE_RULES: Tuple[str, ...] = (
    "You NEVER lecture or explain the answer",
    "You NEVER repeat what the candidate just said back to them",
    "You NEVER ask two questions in one response",
    "Maximum 2 sentences in your response",
    "Sound human, not like a bot reading a script",
)

# Shared framing for who the interviewer is talking to. Part of the assessment
# context rather than the persona, so it is fixed across profiles.
INTERVIEW_CONTEXT = (
    "a professional interviewer conducting a campus placement interview "
    "for an engineering student"
)


@dataclass(frozen=True)
class VoiceSettings:
    """TTS configuration for an interviewer.

    Field names mirror the Sarvam Bulbul parameters so this can be splatted
    into the client call without translation. ``provider`` exists so a future
    profile can point at a different TTS backend without changing callers.
    """

    speaker: str
    provider: str = "sarvam"
    model: str = "bulbul:v3"
    language_code: str = "en-IN"
    # Slightly under 1.0 — measured as clearer for candidates listening over
    # laptop speakers in a noisy room.
    pace: float = 0.95

    def cache_signature(self) -> str:
        """Identity of this voice for cache-key purposes.

        The TTS cache is keyed on text *and* this signature. Without it, the
        first interviewer to synthesise a given sentence would poison the cache
        for every other interviewer — the candidate would hear the wrong voice.
        """
        return f"{self.provider}:{self.model}:{self.language_code}:{self.speaker}:{self.pace}"


@dataclass(frozen=True)
class PersonaSettings:
    """How an interviewer speaks.

    Attributes:
        traits: Short descriptors rendered as the "Your personality" bullets in
            the interviewer prompt. Keep them about *manner*, never about
            standards or strictness — "concise and businesslike" is fine,
            "expects detailed answers" is not, because the latter leaks into
            how the model judges the candidate.
        transition_hint: Optional nudge for how this interviewer moves between
            questions, appended to the transition instruction.
    """

    traits: Tuple[str, ...]
    transition_hint: Optional[str] = None

    def describe(self) -> str:
        """Render the personality block for the interviewer system prompt."""
        return "\n".join(f"- {trait}" for trait in self.traits)


@dataclass(frozen=True)
class InterviewerProfile:
    """A selectable interviewer.

    Attributes:
        id: Stable slug persisted on the session. Never reuse or rename an id
            once sessions reference it.
        name: Display name shown to the candidate.
        title: Role line, e.g. "Senior Engineering Manager".
        tagline: One-line description for the selection card.
        avatar_initials: Fallback avatar text when no image is configured.
        accent: Tailwind colour family used for the selection card accent.
        voice: TTS settings.
        persona: Speaking style.
        greeting: Opening line. Supports ``{name}`` for the interviewer's own
            name; no candidate data is interpolated.
    """

    id: str
    name: str
    title: str
    tagline: str
    avatar_initials: str
    accent: str
    voice: VoiceSettings
    persona: PersonaSettings
    greeting: str

    def render_greeting(self) -> str:
        """Produce the spoken opening line."""
        return self.greeting.format(name=self.name)

    def system_identity(self) -> str:
        """First line of the interviewer system prompt."""
        return f"You are {self.name}, {INTERVIEW_CONTEXT}."

    def style_block(self) -> str:
        """Full personality section: profile traits plus invariant rules."""
        invariants = "\n".join(f"- {rule}" for rule in INVARIANT_STYLE_RULES)
        return f"{self.persona.describe()}\n{invariants}"


# ── The roster ─────────────────────────────────────────────────────────────
# Order here is the order shown in the selection UI.

_PROFILE_LIST: Tuple[InterviewerProfile, ...] = (
    InterviewerProfile(
        id="arjun",
        name="Arjun",
        title="Engineering Manager",
        tagline="Warm and encouraging, keeps the conversation moving.",
        avatar_initials="AR",
        accent="indigo",
        voice=VoiceSettings(speaker="shubh"),
        # These three traits reproduce the interviewer the platform shipped
        # before profiles existed. Changing them changes the default
        # experience for every candidate — treat as a product decision.
        persona=PersonaSettings(
            traits=(
                "Warm but professional",
                "Encouraging but honest",
                "Direct without being harsh",
            ),
        ),
        greeting=(
            "Hi, I'm {name}. Thanks for making the time today — "
            "let's start with a quick introduction."
        ),
    ),
    InterviewerProfile(
        id="kavya",
        name="Kavya",
        title="Senior Technical Interviewer",
        tagline="Precise and structured, focuses on how you reason.",
        avatar_initials="KA",
        accent="violet",
        voice=VoiceSettings(speaker="kavya", pace=0.92),
        persona=PersonaSettings(
            traits=(
                "Calm and measured",
                "Precise in how you phrase things",
                "Curious about reasoning rather than conclusions",
            ),
            transition_hint="Prefer crisp, low-key transitions over enthusiasm.",
        ),
        greeting=(
            "Hello, I'm {name}. I'll be taking you through this round — "
            "shall we begin?"
        ),
    ),
    InterviewerProfile(
        id="ishita",
        name="Ishita",
        title="Director of Talent",
        tagline="Formal and composed, a senior-panel feel.",
        avatar_initials="IS",
        accent="slate",
        voice=VoiceSettings(speaker="ishita", pace=0.9),
        persona=PersonaSettings(
            traits=(
                "Formal and composed",
                "Courteous without being chatty",
                "Steady pace, never rushed",
            ),
            transition_hint="Keep transitions brief and businesslike.",
        ),
        greeting=(
            "Good to meet you. I'm {name}, and I'll be conducting "
            "your interview today."
        ),
    ),
    InterviewerProfile(
        id="priya",
        name="Priya",
        title="Campus Recruiter",
        tagline="Friendly and relaxed, good for settling nerves.",
        avatar_initials="PR",
        accent="emerald",
        voice=VoiceSettings(speaker="priya", pace=1.0),
        persona=PersonaSettings(
            traits=(
                "Friendly and approachable",
                "Naturally conversational",
                "Quick to put a nervous candidate at ease",
            ),
            transition_hint="Transitions can be light and informal.",
        ),
        greeting=(
            "Hey, I'm {name} — really glad you could join. "
            "Let's just have a conversation."
        ),
    ),
)

_PROFILES: Dict[str, InterviewerProfile] = {p.id: p for p in _PROFILE_LIST}

# The interviewer used when a session has no explicit choice — including every
# session created before interviewer selection existed, whose interviewer_id is
# NULL. Its persona intentionally matches the pre-selection behaviour so those
# sessions read back exactly as they were conducted.
DEFAULT_INTERVIEWER_ID = "arjun"


# ── Accessors ──────────────────────────────────────────────────────────────
# The whole public surface. Swapping to a DB-backed store means reimplementing
# these; no caller touches _PROFILES directly.


def list_interviewers() -> List[InterviewerProfile]:
    """Return every selectable interviewer, in display order."""
    return list(_PROFILE_LIST)


def is_valid_interviewer_id(interviewer_id: Optional[str]) -> bool:
    """Return True if the id maps to a known interviewer."""
    return interviewer_id in _PROFILES


def get_interviewer(interviewer_id: Optional[str]) -> InterviewerProfile:
    """Resolve an interviewer id to a profile, always returning something.

    ``None`` means "no choice was recorded" and resolves to the default — this
    is the normal path for sessions created before interviewer selection
    existed, not an error.

    An unknown id is logged and also falls back to the default. A profile that
    was retired between a session starting and its report being generated must
    not make that session unreadable; the interview's scores do not depend on
    the interviewer, so degrading to the default is always safe.
    """
    if interviewer_id is None:
        return _PROFILES[DEFAULT_INTERVIEWER_ID]

    profile = _PROFILES.get(interviewer_id)
    if profile is None:
        logger.warning(
            "Unknown interviewer_id %r; falling back to %r",
            interviewer_id,
            DEFAULT_INTERVIEWER_ID,
        )
        return _PROFILES[DEFAULT_INTERVIEWER_ID]

    return profile


def resolve_selection(interviewer_id: Optional[str]) -> str:
    """Normalise a candidate's selection into an id safe to persist.

    Use at the point of session creation so the database never stores an id
    that cannot be resolved later.
    """
    return get_interviewer(interviewer_id).id
