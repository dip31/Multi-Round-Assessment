"""
Aptitude router stub.

Endpoints for fetching questions, submitting answers, and RL-driven
difficulty adaptation will be added here.
"""

from fastapi import APIRouter

router = APIRouter(prefix="/aptitude", tags=["Aptitude Round"])


# TODO: GET  /questions    – fetch next question (RL-selected difficulty)
# TODO: POST /attempt      – submit an answer
# TODO: GET  /results      – round analytics
