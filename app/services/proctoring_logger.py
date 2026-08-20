import asyncio
import logging
from collections import deque
from threading import Lock
from typing import Any, Dict, Optional

from sqlalchemy.exc import SQLAlchemyError

from app.models.interview import ProctoringViolation

LOGGER = logging.getLogger("app.services.proctoring_logger")

# In-memory queue for failed writes
_QUEUE: deque = deque(maxlen=50)
_QUEUE_LOCK = Lock()


async def _write_violation(db, item: Dict[str, Any]) -> bool:
    try:
        v = ProctoringViolation(
            session_id=item["session_id"],
            event_type=item["event_type"],
            confidence_score=item.get("confidence_score"),
            face_count=item.get("face_count"),
            violation_metadata=item.get("metadata"),
        )
        db.add(v)
        db.commit()
        db.refresh(v)
        return True
    except SQLAlchemyError as e:
        LOGGER.warning("proctoring_logger: db write failed: %s", e)
        try:
            db.rollback()
        except Exception:
            pass
        return False
    except Exception as e:
        LOGGER.exception("proctoring_logger: unexpected error: %s", e)
        try:
            db.rollback()
        except Exception:
            pass
        return False


async def flush_queue(db) -> int:
    """Attempt to flush queued violations. Returns number successfully written."""
    written = 0
    # Make a local copy to avoid holding lock during DB ops
    with _QUEUE_LOCK:
        items = list(_QUEUE)
        _QUEUE.clear()

    for item in items:
        ok = await _write_violation(db, item)
        if ok:
            written += 1
        else:
            # re-queue failed items
            with _QUEUE_LOCK:
                _QUEUE.appendleft(item)
            break

    if written:
        LOGGER.info("proctoring_logger: flushed %d queued violations", written)
    return written


async def log_violation(db, session_id: int, event_type: str, confidence_score: Optional[float] = None, face_count: Optional[int] = None, metadata: Optional[dict] = None) -> bool:
    """Attempt to write a violation record with retry logic. Returns True if logged immediately; False if queued."""
    item = {
        "session_id": session_id,
        "event_type": event_type,
        "confidence_score": confidence_score,
        "face_count": face_count,
        "metadata": metadata or {},
    }

    delays = [0, 1, 2]
    for delay in delays:
        if delay:
            await asyncio.sleep(delay)
        ok = await _write_violation(db, item)
        if ok:
            # On success, try to flush any queued items
            try:
                await flush_queue(db)
            except Exception:
                pass
            return True

    # All retries failed — queue the item
    with _QUEUE_LOCK:
        # deque with maxlen will drop oldest when full
        _QUEUE.append(item)
        LOGGER.warning("proctoring_logger: queued violation (queue_size=%d)", len(_QUEUE))

    return False
