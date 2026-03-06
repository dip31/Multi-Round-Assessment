"""
Coding router stub.

Endpoints for fetching coding problems, submitting code, and retrieving
Judge0 results will be added here.
"""

from fastapi import APIRouter

router = APIRouter(prefix="/coding", tags=["Coding Round"])


# TODO: GET  /problems          – list coding problems for the round
# TODO: POST /submit            – submit code for execution
# TODO: GET  /submission/{id}   – poll Judge0 result
