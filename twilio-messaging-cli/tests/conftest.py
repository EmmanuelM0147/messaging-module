"""Keep tests off the real Twilio API and off real .env credentials."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest


@pytest.fixture(autouse=True)
def isolated_env(monkeypatch: pytest.MonkeyPatch) -> MagicMock:
    monkeypatch.setattr("twilio_send._load_env", lambda: None)
    monkeypatch.delenv("TWILIO_ACCOUNT_SID", raising=False)
    monkeypatch.delenv("TWILIO_AUTH_TOKEN", raising=False)
    monkeypatch.delenv("TWILIO_WHATSAPP_FROM", raising=False)
    monkeypatch.delenv("TWILIO_SMS_FROM", raising=False)
    monkeypatch.setenv("TWILIO_ACCOUNT_SID", "ACxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx")
    monkeypatch.setenv("TWILIO_AUTH_TOKEN", "test_auth_token")
    monkeypatch.setenv("TWILIO_WHATSAPP_FROM", "whatsapp:+14155238886")
    monkeypatch.setenv("TWILIO_SMS_FROM", "+15557654321")

    client = MagicMock(name="TwilioClient")
    client.messages.create.side_effect = AssertionError(
        "unmocked Twilio API call - tests must not hit the network"
    )
    monkeypatch.setattr("twilio_send.build_client", lambda: client)
    monkeypatch.setattr(
        "twilio_send.Client",
        MagicMock(
            side_effect=AssertionError(
                "unmocked Twilio Client() - tests must not hit the network"
            )
        ),
    )
    return client


@pytest.fixture
def twilio_client(isolated_env: MagicMock) -> MagicMock:
    isolated_env.messages.create.side_effect = None
    return isolated_env
