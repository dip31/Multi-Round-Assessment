from fastapi.testclient import TestClient
from app.main import app
from app.database.db import SessionLocal
from app.models.user import User
from app.core.auth import get_current_user

db = SessionLocal()
user = db.query(User).first()
if not user:
    user = User(email="test2@example.com", name="test2")
    db.add(user)
    db.commit()
    db.refresh(user)

def override_get_current_user():
    return user

app.dependency_overrides[get_current_user] = override_get_current_user

client = TestClient(app)

print("--- POST /api/v1/session/fresh ---")
res = client.post("/api/v1/session/fresh")
print("Status:", res.status_code)
print("Response:", res.json())

print("--- GET /api/v1/session/status ---")
res2 = client.get("/api/v1/session/status")
print("Status:", res2.status_code)
print("Response:", res2.json())

print("--- GET /api/v1/aptitude/next-question ---")
res3 = client.get("/api/v1/aptitude/next-question?practice_type=mcq")
print("Status:", res3.status_code)
print("Response:", res3.json())
