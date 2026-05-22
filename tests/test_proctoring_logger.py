import pytest
import asyncio

from app.services import proctoring_logger as pl


class FakeDB:
    def __init__(self, fail=False):
        self.fail = fail

    def add(self, obj):
        if self.fail:
            raise Exception("db add failed")

    def commit(self):
        if self.fail:
            raise Exception("commit failed")

    def refresh(self, obj):
        return

    def rollback(self):
        return


@pytest.mark.asyncio
async def test_log_violation_success():
    db = FakeDB(fail=False)
    ok = await pl.log_violation(db, session_id=1, event_type="phone_detected", confidence_score=0.9)
    assert ok is True


@pytest.mark.asyncio
async def test_log_violation_queued_on_failure():
    db = FakeDB(fail=True)
    ok = await pl.log_violation(db, session_id=2, event_type="phone_detected", confidence_score=0.5)
    assert ok is False
