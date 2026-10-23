import json

from sqlalchemy import Column, Integer, MetaData, Table, create_engine
from sqlalchemy.orm import Session

from app.models.proctoring import ProctoringEvent
from app.services.proctoring_service import log_proctoring_event, stop_proctoring_session


def make_database():
    engine = create_engine("sqlite:///:memory:")
    metadata = MetaData()
    Table("assessment_sessions", metadata, Column("id", Integer, primary_key=True))
    metadata.create_all(engine)
    ProctoringEvent.__table__.create(engine)
    return engine


def test_log_proctoring_event_serializes_metadata_as_json():
    engine = make_database()
    with Session(engine) as db:
        event = log_proctoring_event(
            db,
            session_id=42,
            event_type="PROCTORING_STOPPED",
            event_metadata={"reason": "round_finished"},
        )

        assert json.loads(event.event_metadata) == {"reason": "round_finished"}
        assert event.metadata_dict == {"reason": "round_finished"}


def test_stop_proctoring_session_is_idempotent():
    engine = make_database()
    with Session(engine) as db:
        first = stop_proctoring_session(db, session_id=42)
        second = stop_proctoring_session(db, session_id=42)

        assert first is not None
        assert second is not None
        assert first.id == second.id
        assert first.event_type == "PROCTORING_STOPPED"
        assert "stopped_at" in second.metadata_dict
