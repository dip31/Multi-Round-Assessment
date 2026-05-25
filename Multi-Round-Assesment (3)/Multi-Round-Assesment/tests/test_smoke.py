"""Quick smoke test for auth and session endpoints using TestClient + in-memory SQLite."""

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database.db import get_db
from app.database.base import Base

# Force-import models so Base.metadata is populated
import app.models.user  # noqa: F401
import app.models.assessment  # noqa: F401

# Import the FastAPI instance as `application` to avoid shadowing `app` package
from app.main import app as application

# ── In-memory SQLite for testing ──────────────────────────────────────
# StaticPool ensures all sessions share the same in-memory database.
engine = create_engine(
    "sqlite:///:memory:",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
Base.metadata.create_all(bind=engine)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def override_get_db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


application.dependency_overrides[get_db] = override_get_db
client = TestClient(application)

# ── Tests ─────────────────────────────────────────────────────────────
passed = 0

# 1. Health check
r = client.get("/health")
assert r.status_code == 200, f"Health failed: {r.status_code}"
passed += 1
print("1. Health check: PASS")

# 2. Register
r = client.post("/api/v1/auth/register", json={"name": "Alice", "email": "alice@test.com", "password": "securepass123"})
assert r.status_code == 201, f"Register failed: {r.status_code} {r.text}"
assert r.json()["email"] == "alice@test.com"
passed += 1
print("2. Register: PASS")

# 3. Duplicate register → 409
r = client.post("/api/v1/auth/register", json={"name": "Alice", "email": "alice@test.com", "password": "securepass123"})
assert r.status_code == 409, f"Duplicate register should be 409: {r.status_code}"
passed += 1
print("3. Duplicate register 409: PASS")

# 4. Login
r = client.post("/api/v1/auth/login", json={"email": "alice@test.com", "password": "securepass123"})
assert r.status_code == 200, f"Login failed: {r.status_code} {r.text}"
token = r.json()["access_token"]
assert len(token) > 0
passed += 1
print("4. Login: PASS")

# 5. Wrong password → 401
r = client.post("/api/v1/auth/login", json={"email": "alice@test.com", "password": "wrongpass"})
assert r.status_code == 401, f"Wrong password should be 401: {r.status_code}"
passed += 1
print("5. Wrong password 401: PASS")

# 6. Session start (authenticated)
headers = {"Authorization": f"Bearer {token}"}
r = client.post("/api/v1/session/start", headers=headers)
assert r.status_code == 201, f"Start session failed: {r.status_code} {r.text}"
session_data = r.json()
assert session_data["status"] == "in_progress"
passed += 1
print("6. Session start: PASS")

# 7. Duplicate session → 409
r = client.post("/api/v1/session/start", headers=headers)
assert r.status_code == 409, f"Duplicate session should be 409: {r.status_code}"
passed += 1
print("7. Duplicate session 409: PASS")

# 8. Session status
r = client.get("/api/v1/session/status", headers=headers)
assert r.status_code == 200, f"Session status failed: {r.status_code}"
assert r.json()["id"] == session_data["id"]
passed += 1
print("8. Session status: PASS")

# 9. Unauthenticated access → 401
r = client.post("/api/v1/session/start")
assert r.status_code == 401, f"Unauth should be 401: {r.status_code}"
passed += 1
print("9. Unauthenticated 401: PASS")

print(f"\nALL {passed}/9 TESTS PASSED")
