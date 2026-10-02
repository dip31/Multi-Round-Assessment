"""
Sarvam AI TTS Service

Converts interview question text to speech using Sarvam Bulbul v3 API.
Integrates Redis caching for efficient repeated audio generation.

Voice parameters are per-call and optional. Omitting them reproduces the
original behaviour exactly (shubh / en-IN / pace 0.95), so callers that do not
care about the interviewer persona need no changes. Callers that do resolve the
voice from the interviewer profile and pass it in; this module stays unaware of
interviewers, profiles, and sessions — it only knows how to speak.
"""

import base64
import hashlib
import logging
import time
from typing import Any, Optional

import redis

try:
    from sarvamai import SarvamAI as _SarvamAI
    SARVAM_AVAILABLE = True
except ImportError:
    _SarvamAI = None

    SARVAM_AVAILABLE = False

from app.config.settings import settings

logger = logging.getLogger(__name__)

SARVAM_API_KEY = settings.SARVAM_API_KEY
REDIS_URL = settings.REDIS_URL

# ── Voice defaults ─────────────────────────────────────────────────────────
# These are the values this service used as inline literals before voices
# became selectable. They remain the fallback so that any caller which passes
# no voice gets byte-identical audio to before.
DEFAULT_SPEAKER = "shubh"        # Clear, professional male voice
DEFAULT_MODEL = "bulbul:v3"
DEFAULT_LANGUAGE_CODE = "en-IN"  # Indian English
DEFAULT_PACE = 0.95              # Slightly slower for clarity

# Not a voice characteristic — it is what the frontend audio player expects,
# so it is fixed rather than per-interviewer.
SPEECH_SAMPLE_RATE = 24000

def _initialize_redis_client() -> Optional[redis.Redis]:
    """Connect to Redis if configured; otherwise keep TTS running without cache."""
    if not REDIS_URL:
        logger.info("Redis TTS cache disabled: REDIS_URL not configured")
        return None

    try:
        client = redis.from_url(REDIS_URL, decode_responses=False)
        client.ping()
        logger.info("Redis cache connected for TTS")
        return client
    except Exception as e:
        logger.info(f"Redis TTS cache unavailable; continuing without cache: {str(e)}")
        return None


redis_client: Optional[redis.Redis] = _initialize_redis_client()

# Initialize Sarvam client
sarvam_client: Optional[Any] = None
if SARVAM_AVAILABLE and SARVAM_API_KEY and _SarvamAI is not None:
    try:
        sarvam_client = _SarvamAI(api_subscription_key=SARVAM_API_KEY)
        logger.info(f"Sarvam client ready: {sarvam_client is not None}, key set: {bool(SARVAM_API_KEY)}")
    except Exception as e:
        logger.error(f"Failed to initialize Sarvam client: {str(e)}")
        sarvam_client = None
else:
    logger.warning(f"Sarvam initialization skipped: available={SARVAM_AVAILABLE}, key_set={bool(SARVAM_API_KEY)}")


def _cache_key(text: str, voice_signature: str) -> str:
    """Generate Redis cache key from text *and* the voice used to speak it.

    The voice signature is not optional decoration. Audio is a function of
    (text, voice); keying on text alone meant the first interviewer to
    synthesise a sentence poisoned the cache for every other interviewer, and
    the candidate would hear somebody else's voice finish their interview.

    Consequence of adding the signature: keys written by the previous
    text-only scheme will never be read again. That is a one-off cold cache,
    not data loss — entries expire in 24h and the only cost is re-synthesis.
    """
    digest = hashlib.md5(text.encode()).hexdigest()
    voice_digest = hashlib.md5(voice_signature.encode()).hexdigest()[:8]
    return f"tts:{voice_digest}:{digest}"


async def text_to_speech(
    text: str,
    *,
    speaker: Optional[str] = None,
    model: Optional[str] = None,
    language_code: Optional[str] = None,
    pace: Optional[float] = None,
) -> bytes:
    """
    Convert text to WAV audio bytes using Sarvam Bulbul v3.

    Checks Redis cache first for faster repeated playback.
    Caches result for 24 hours (86400 seconds).

    Args:
        text: Interview question text (max 2500 chars)
        speaker: Sarvam voice name. Defaults to DEFAULT_SPEAKER.
        model: Sarvam TTS model. Defaults to DEFAULT_MODEL.
        language_code: BCP-47 language tag. Defaults to DEFAULT_LANGUAGE_CODE.
        pace: Speech rate multiplier. Defaults to DEFAULT_PACE.

    Voice arguments are keyword-only so that existing positional callers keep
    working untouched, and ``None`` means "use the default" rather than being
    forwarded to the API as a null.

    Returns:
        Raw WAV audio bytes (ArrayBuffer for frontend)

    Raises:
        Exception: If API key missing, text too long, rate limited, or service unavailable
    """

    if not SARVAM_API_KEY:
        raise Exception(
            "Sarvam API key not configured. "
            "Set SARVAM_API_KEY environment variable."
        )

    if not sarvam_client:
        raise Exception(
            "Sarvam AI client not initialized. "
            "Check API key and sarvamai package installation."
        )

    if len(text) > 2500:
        raise Exception("Text too long for TTS (max 2500 characters)")

    # Resolve once, up front, so the cache key and both convert() calls below
    # (including the 422 retry) are guaranteed to agree on the voice. They
    # drifted apart when these values were inline literals.
    voice_speaker = speaker or DEFAULT_SPEAKER
    voice_model = model or DEFAULT_MODEL
    voice_language_code = language_code or DEFAULT_LANGUAGE_CODE
    voice_pace = DEFAULT_PACE if pace is None else pace

    # Check Redis cache
    cache_key = _cache_key(
        text,
        f"{voice_model}:{voice_language_code}:{voice_speaker}:{voice_pace}",
    )
    if redis_client:
        try:
            cached = redis_client.get(cache_key)
            if isinstance(cached, (bytes, bytearray)):
                logger.debug(f"TTS cache hit for text: {text[:50]}...")
                return bytes(cached)
        except Exception as e:
            logger.warning(f"Redis cache get failed: {str(e)}")

    # Call Sarvam API
    logger.info(f"TTS request: text_len={len(text)}, speaker={voice_speaker}")
    t0 = time.monotonic()

    try:
        response = sarvam_client.text_to_speech.convert(
            text=text,
            model=voice_model,
            language_code=voice_language_code,
            speaker=voice_speaker,
            pace=voice_pace,
            speech_sample_rate=SPEECH_SAMPLE_RATE,
        )
        
        # response.audios is list of base64-encoded WAV strings
        if not response.audios or len(response.audios) == 0:
            raise Exception("Sarvam returned empty audio list")
        
        audio_bytes = base64.b64decode(response.audios[0])
        
        logger.info(f"TTS success: audios_count={len(response.audios)}, bytes={len(audio_bytes)}, latency={time.monotonic()-t0:.2f}s")
        
        # Cache in Redis for 24 hours
        if redis_client:
            try:
                redis_client.setex(cache_key, 86400, audio_bytes)
                logger.debug("TTS result cached in Redis")
            except Exception as e:
                logger.warning(f"Redis cache set failed: {str(e)}")
        
        return audio_bytes
        
    except Exception as e:
        status_code = getattr(e, "status_code", None)
        logger.error(f"Sarvam TTS failed: type={type(e).__name__}, status={status_code}")
        body = getattr(e, "body", str(e))

        if status_code == 429:
            raise Exception(
                "TTS rate limit exceeded. Please try again in a few moments."
            )
        elif status_code == 403:
            raise Exception(
                "Invalid Sarvam API key. Check SARVAM_API_KEY in .env"
            )
        elif status_code == 422:
            # Text validation error — try truncating
            logger.warning(f"Sarvam returned 422 for text: {text[:100]}...")
            truncated = text[:2400]
            try:
                response = sarvam_client.text_to_speech.convert(
                    text=truncated,
                    model=voice_model,
                    language_code=voice_language_code,
                    speaker=voice_speaker,
                    pace=voice_pace,
                    speech_sample_rate=SPEECH_SAMPLE_RATE,
                )
                audio_bytes = base64.b64decode(response.audios[0])
                
                # Cache truncated result
                if redis_client:
                    try:
                        redis_client.setex(cache_key, 86400, audio_bytes)
                    except Exception:
                        pass
                
                logger.info("TTS succeeded after text truncation")
                return audio_bytes
            except Exception as retry_e:
                raise Exception(f"TTS failed even after truncation: {str(retry_e)}")
        else:
            raise Exception(f"Sarvam TTS error {status_code}: {str(body)}")


def get_voice_options() -> dict:
    """
    Get available Sarvam Bulbul v3 voices for interview context.

    This describes what the TTS provider can speak. It is NOT the list of
    interviewers a candidate can choose — that roster lives in
    ``app/modules/interview/config/interviewer_profiles.py`` and is served by
    ``GET /interview/interviewers``. Do not build selection UI from this.

    Returns:
        Dict mapping voice names to descriptions
    """
    return {
        "shubh": "Clear, professional male voice (recommended for formal interviews)",
        "kavya": "Confident and clear female voice",
        "ishita": "Professional female tone",
        "priya": "Natural and warm female voice",
    }
