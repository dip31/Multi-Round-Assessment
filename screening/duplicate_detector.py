"""
Duplicate Detector — identifies duplicate candidate profiles within the same job.

Matches by:
  1. Exact email
  2. Exact phone
  3. Fuzzy name similarity (>85%)
"""
import logging
from difflib import SequenceMatcher
from shared.db.models import Candidate
from sqlalchemy import select

try:
    from fuzzywuzzy import fuzz
except ImportError:
    class fuzz:
        @staticmethod
        def ratio(left: str, right: str) -> int:
            return round(SequenceMatcher(None, left, right).ratio() * 100)

logger = logging.getLogger(__name__)

FUZZY_NAME_THRESHOLD = 85


def check_duplicate(candidate, db_session):
    """
    Check if `candidate` is a duplicate of any existing candidate for the same job.

    Args:
        candidate: Candidate ORM object (the new one being screened).
        db_session: Active SQLAlchemy session.

    Returns:
        (is_duplicate: bool, original_id: str | None)
    """
    # Only compare against other candidates for the same job
    existing = (
        db_session.query(Candidate)
        .filter(
            Candidate.job_id == candidate.job_id,
            Candidate.id != candidate.id,
            Candidate.is_duplicate == False,       # don't match against other dupes
        )
        .all()
    )

    for other in existing:
        # 1. Exact email match
        if candidate.email and other.email:
            if candidate.email.strip().lower() == other.email.strip().lower():
                logger.info("Duplicate detected (email): %s == %s", candidate.email, other.email)
                return True, other.id

        # 2. Exact phone match
        if candidate.phone and other.phone:
            c_phone = candidate.phone.strip().replace(" ", "").replace("-", "")
            o_phone = other.phone.strip().replace(" ", "").replace("-", "")
            if c_phone == o_phone:
                logger.info("Duplicate detected (phone): %s == %s", candidate.phone, other.phone)
                return True, other.id

        # 3. Fuzzy name match
        if candidate.name and other.name:
            ratio = fuzz.ratio(candidate.name.strip().lower(), other.name.strip().lower())
            if ratio > FUZZY_NAME_THRESHOLD:
                logger.info(
                    "Duplicate detected (fuzzy name %d%%): '%s' ≈ '%s'",
                    ratio, candidate.name, other.name,
                )
                return True, other.id

    return False, None


async def check_duplicate_async(candidate, db_session):
    """
    Async version of duplicate detection for use with AsyncSession.

    Args:
        candidate: Candidate ORM object (the new one being screened).
        db_session: Active AsyncSession.

    Returns:
        (is_duplicate: bool, original_id: str | None)
    """
    # Only compare against other candidates for the same job
    result = await db_session.execute(
        select(Candidate).where(
            Candidate.job_id == candidate.job_id,
            Candidate.id != candidate.id,
            Candidate.is_duplicate == False,
        )
    )
    existing = result.scalars().all()

    for other in existing:
        # 1. Exact email match
        if candidate.email and other.email:
            if candidate.email.strip().lower() == other.email.strip().lower():
                logger.info("Duplicate detected (email): %s == %s", candidate.email, other.email)
                return True, other.id

        # 2. Exact phone match
        if candidate.phone and other.phone:
            c_phone = candidate.phone.strip().replace(" ", "").replace("-", "")
            o_phone = other.phone.strip().replace(" ", "").replace("-", "")
            if c_phone == o_phone:
                logger.info("Duplicate detected (phone): %s == %s", candidate.phone, other.phone)
                return True, other.id

        # 3. Fuzzy name match
        if candidate.name and other.name:
            ratio = fuzz.ratio(candidate.name.strip().lower(), other.name.strip().lower())
            if ratio > FUZZY_NAME_THRESHOLD:
                logger.info(
                    "Duplicate detected (fuzzy name %d%%): '%s' ≈ '%s'",
                    ratio, candidate.name, other.name,
                )
                return True, other.id

    return False, None
