import asyncio

import pytest
from fastapi import HTTPException

from app.modules.interview.routers.interviewer_management import preview_voice


def test_retell_voice_preview_is_rejected_as_not_sarvam():
    with pytest.raises(HTTPException) as error:
        asyncio.run(
            preview_voice(
                voice_id="retell-Cimo",
                text="Retell preview",
                current_user=None,
            )
        )

    assert error.value.status_code == 400
    assert "Only Sarvam voices" in error.value.detail
