import asyncio
import pytest

from types import SimpleNamespace

from app.modules.interview.routers.interview_router import analyze_frame, log_event


class FakeUpload:
    def __init__(self, data: bytes):
        self._data = data

    async def read(self):
        return self._data


class FakeDB:
    """In-memory DB stub for analyze_frame / log_event router tests.

    Returns the appropriate "row" based on which ORM model is queried, so
    the router's ownership check (which fetches AssessmentSession -> user_id)
    has the field it needs. Does NOT weaken the authorization check in
    production code — only feeds the fixture the columns that code reads.
    """

    def __init__(self):
        pass

    def query(self, model, *args, **kwargs):
        # Capture the queried model class so each filter().first() returns a
        # row shaped like that model. The router exercises two lookups:
        #   db.query(InterviewSession)  -> needs id, session_id
        #   db.query(AssessmentSession) -> needs id, user_id
        class Q:
            def __init__(self, model_cls):
                self._model = model_cls

            def filter(self, *a, **k):
                return self

            def first(self):
                # Import lazily so package imports above don't wire the ORM.
                from app.models.interview import InterviewSession
                from app.models.assessment import AssessmentSession
                if self._model is AssessmentSession:
                    # fake.owner = current_user.id == 1 (see FakeUser)
                    return SimpleNamespace(id=1, user_id=1)
                if self._model is InterviewSession:
                    # InterviewSession.id=123, session_id=1 matches AssessmentSession.id=1
                    return SimpleNamespace(id=123, session_id=1)
                # Unknown model: return a benign row that won't match anything
                return SimpleNamespace(id=1)

        return Q(model)


class FakeUser:
    def __init__(self):
        self.id = 1
        self.role = 'admin'


@pytest.mark.asyncio
async def test_analyze_frame_calls_detection(monkeypatch):
    # Monkeypatch detect_phones to return a fake detection
    monkeypatch.setattr('app.modules.interview.routers.interview_router.detect_phones', lambda b: [{"confidence": 0.9, "bbox": [1,2,3,4]}])

    # Monkeypatch log_violation to an async stub
    async def fake_log(db, session_id, event_type, confidence_score=None, face_count=None, metadata=None):
        return True

    monkeypatch.setattr('app.modules.interview.routers.interview_router.log_violation', fake_log)

    frame = FakeUpload(b"\xff\xd8\xff\xd9")
    db = FakeDB()
    user = FakeUser()

    res = await analyze_frame(frame=frame, session_id=123, db=db, current_user=user)
    assert 'violations' in res
    assert res['phone_count'] == 1


@pytest.mark.asyncio
async def test_log_event_endpoint(monkeypatch):
    async def fake_log(db, session_id, event_type, confidence_score=None, face_count=None, metadata=None):
        return True

    monkeypatch.setattr('app.modules.interview.routers.interview_router.log_violation', fake_log)

    req = SimpleNamespace(session_id=123, event_type='phone_detected', confidence_score=0.8, face_count=None, metadata={})
    db = FakeDB()
    user = FakeUser()

    res = await log_event(req, db=db, current_user=user)
    assert res['status'] in ('logged', 'queued')
