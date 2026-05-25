"""
Sarvam AI TTS Service

Converts interview question text to speech using Sarvam Bulbul v3 API.
Integrates Redis caching for efficient repeated audio generation.

Voice: shubh (clear, professional male voice, suitable for formal interviews)
Language: en-IN (Indian English)
"""

import base64
import hashlib
import logging
from typing import Optional

import redis

try:
    from sarvamai import SarvamAI
    from sarvamai.core.api_error import ApiError
    SARVAM_AVAILABLE = True
except ImportError:
    SARVAM_AVAILABLE = False

from config import *

logger = logging.getLogger(__name__)

SARVAM_API_KEY = SARVAM_API_KEY
REDIS_URL = settings.REDIS_URL

# Initialize Redis client
redis_client: Optional[redis.Redis] = None
try:
    redis_client = redis.from_url(REDIS_URL, decode_responses=False)
    # Test connection
    redis_client.ping()
    logger.info("Redis cache connected for TTS")
except Exception as e:
    logger.warning(f"Redis TTS cache unavailable: {str(e)}")
    redis_client = None

# Initialize Sarvam client
sarvam_client: Optional[SarvamAI] = None
if SARVAM_AVAILABLE and SARVAM_API_KEY:
    try:
        sarvam_client = SarvamAI(api_subscription_key=SARVAM_API_KEY)
        logger.info("Sarvam AI client initialized")
    except Exception as e:
        logger.error(f"Failed to initialize Sarvam client: {str(e)}")
        sarvam_client = None


def _cache_key(text: str) -> str:
    """Generate Redis cache key from text."""
    return f"tts:{hashlib.md5(text.encode()).hexdigest()}"


async def text_to_speech(text: str) -> bytes:
    """
    Convert text to WAV audio bytes using Sarvam Bulbul v3.
    
    Checks Redis cache first for faster repeated playback.
    Caches result for 24 hours (86400 seconds).
    
    Args:
        text: Interview question text (max 2500 chars)
        
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
    
    # Check Redis cache
    cache_key = _cache_key(text)
    if redis_client:
        try:
            cached = redis_client.get(cache_key)
            if cached:
                logger.debug(f"TTS cache hit for text: {text[:50]}...")
                return cached
        except Exception as e:
            logger.warning(f"Redis cache get failed: {str(e)}")
    
    # Call Sarvam API
    try:
        logger.debug(f"Calling Sarvam TTS for: {text[:50]}...")
        response = sarvam_client.text_to_speech.convert(
            text=text,
            model="bulbul:v3",
            target_language_code="en-IN",
            speaker="shubh",  # Clear, professional male voice
            pace=0.95,        # Slightly slower for clarity
            speech_sample_rate=24000,
        )
        
        # response.audios is list of base64-encoded WAV strings
        if not response.audios or len(response.audios) == 0:
            raise Exception("Sarvam returned empty audio list")
        
        audio_bytes = base64.b64decode(response.audios[0])
        
        # Cache in Redis for 24 hours
        if redis_client:
            try:
                redis_client.setex(cache_key, 86400, audio_bytes)
                logger.debug("TTS result cached in Redis")
            except Exception as e:
                logger.warning(f"Redis cache set failed: {str(e)}")
        
        return audio_bytes
        
    except ApiError as e:
        if e.status_code == 429:
            raise Exception(
                "TTS rate limit exceeded. Please try again in a few moments."
            )
        elif e.status_code == 403:
            raise Exception(
                "Invalid Sarvam API key. Check SARVAM_API_KEY in .env"
            )
        elif e.status_code == 422:
            # Text validation error — try truncating
            logger.warning(f"Sarvam returned 422 for text: {text[:100]}...")
            truncated = text[:2400]
            try:
                response = sarvam_client.text_to_speech.convert(
                    text=truncated,
                    model="bulbul:v3",
                    target_language_code="en-IN",
                    speaker="shubh",
                    pace=0.95,
                    speech_sample_rate=24000,
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
            raise Exception(f"Sarvam TTS error {e.status_code}: {str(e.body)}")
    
    except Exception as e:
        logger.error(f"Unexpected Sarvam TTS error: {str(e)}")
        raise Exception(f"TTS service error: {str(e)}")


def get_voice_options() -> dict:
    """
    Get available Sarvam Bulbul v3 voices for interview context.
    
    Returns:
        Dict mapping voice names to descriptions
    """
    return {
        "shubh": "Clear, professional male voice (recommended for formal interviews)",
        "kavya": "Confident and clear female voice",
        "ishita": "Professional female tone",
        "priya": "Natural and warm female voice",
    }

