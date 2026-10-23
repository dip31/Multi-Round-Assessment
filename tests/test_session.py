import asyncio
from sqlalchemy.orm import Session
from app.database.db import SessionLocal
from app.services.session_service import get_active_session, create_session, _now
from app.models.user import User
from app.models.assessment import AssessmentSession

db = SessionLocal()
user = db.query(User).first()
if not user:
    user = User(email="test@example.com", name="test")
    db.add(user)
    db.commit()
    db.refresh(user)

old = db.query(AssessmentSession).filter_by(user_id=user.id).all()
for o in old:
    o.status = "completed"
db.commit()

session = create_session(db, user_id=user.id)
print("Created session:", session.id)
print("Started at:", session.started_at)
print("Expires at:", session.expires_at)
print("Now:", _now())
print("Time remaining seconds (prop):", session.time_remaining_seconds)

active = get_active_session(db, user_id=user.id)
print("Active session:", active.id if active else None)
print("Active time remaining:", active.time_remaining_seconds if active else None)

from app.schemas.assessment import SessionResponse
resp = SessionResponse.model_validate(active)
print("Serialized time remaining:", resp.time_remaining_seconds)
