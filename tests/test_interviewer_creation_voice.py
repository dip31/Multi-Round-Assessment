import asyncio

import pytest

from app.modules.interview.services.interviewer_service import (
    InterviewerCreateRequest,
    InterviewerService,
    InterviewerServiceError,
    build_retell_agent_create_args,
)


def test_agent_creation_omits_empty_optional_voice_model():
    args = build_retell_agent_create_args(
        llm_id="llm-test",
        name="Test interviewer",
        voice_id="retell-Cimo",
        voice_model="",
    )

    assert args["voice_id"] == "retell-Cimo"
    assert args["response_engine"]["llm_id"] == "llm-test"
    assert "voice_model" not in args


def test_agent_creation_includes_nonempty_voice_model_trimmed():
    args = build_retell_agent_create_args(
        llm_id="llm-test",
        name="Test interviewer",
        voice_id="retell-Cimo",
        voice_model=" model-id ",
    )

    assert args["voice_model"] == "model-id"


def test_sarvam_voice_is_rejected_before_retell_api_call():
    service = InterviewerService(db=None)
    request = InterviewerCreateRequest(
        name="Test interviewer",
        title="Interviewer",
        tagline="Test tagline",
        personality="calm",
        speaking_style="clear",
        greeting="Hello",
        avatar_initials="TI",
        voice_id="shubh",
    )

    with pytest.raises(InterviewerServiceError, match="Choose a Retell voice"):
        asyncio.run(service.create_interviewer(request))
