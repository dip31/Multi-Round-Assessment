import asyncio

from app.config.settings import settings
from app.modules.interview.routers.interview_router import get_voice_modes
from app.modules.interview.services.retell_adapter import RetellAdapter, RetellCallConfig


class _FakeRetellResponse:
    def raise_for_status(self):
        pass

    @staticmethod
    def json():
        return {
            "call_id": "call-test",
            "access_token": "token-test",
            "transport": "webrtc",
            "ice_servers": [],
            "expires_at": 1,
        }


class _FakeRetellClient:
    def __init__(self):
        self.payload = None

    async def post(self, path, json):
        self.payload = json
        return _FakeRetellResponse()


def test_hosted_mode_does_not_require_custom_websocket(monkeypatch):
    monkeypatch.setattr(settings, "RETELL_API_KEY", "configured")
    monkeypatch.setattr(settings, "RETELL_AGENT_ID", "configured")
    monkeypatch.setattr(settings, "RETELL_LLM_WEBSOCKET_URL", "")

    modes = asyncio.run(get_voice_modes(current_user=None))

    assert modes["retell_hosted"]["available"] is True
    assert modes["edi5_core"]["available"] is False
    assert "RETELL_LLM_WEBSOCKET_URL" in modes["edi5_core"]["reason"]


def test_core_mode_available_requires_retell_credentials_and_websocket(monkeypatch):
    monkeypatch.setattr(settings, "RETELL_API_KEY", "configured")
    monkeypatch.setattr(settings, "RETELL_AGENT_ID", "configured")
    monkeypatch.setattr(settings, "RETELL_LLM_WEBSOCKET_URL", "wss://backend.example/ws")

    modes = asyncio.run(get_voice_modes(current_user=None))

    assert modes["retell_hosted"]["available"] is True
    assert modes["edi5_core"]["available"] is True

    monkeypatch.setattr(settings, "RETELL_API_KEY", "")
    modes = asyncio.run(get_voice_modes(current_user=None))
    assert modes["retell_hosted"]["available"] is False
    assert modes["edi5_core"]["available"] is False


def test_hosted_call_does_not_send_a_custom_llm_websocket():
    adapter = RetellAdapter.__new__(RetellAdapter)
    client = _FakeRetellClient()
    adapter._client = client

    asyncio.run(adapter.create_web_call(
        RetellCallConfig(agent_id="agent-test", agent_override={"retell_llm": {}})
    ))

    assert client.payload["agent_id"] == "agent-test"
    assert "response_engine" not in client.payload["agent_override"]
