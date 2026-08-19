from __future__ import annotations

import sys
from unittest.mock import MagicMock

import pytest
import requests
from twilio.base.exceptions import TwilioRestException

import twilio_send


def _run_main(monkeypatch: pytest.MonkeyPatch, *argv: str) -> int:
    monkeypatch.setattr(sys, "argv", ["twilio_send", *argv])
    with pytest.raises(SystemExit) as caught:
        twilio_send.main()
    return int(caught.value.code)


@pytest.mark.parametrize(
    "number",
    (
        "+15551234567",
        "+14155552671",
        "+2348139608051",
        "+447911123456",
    ),
)
def test_valid_e164_passes_validation(number: str) -> None:
    assert twilio_send.validate_e164(number) is True


@pytest.mark.parametrize(
    "number",
    (
        "15551234567",
        "+0123456789",
        "08139608051",
        "+1",
        "+",
        "",
        "not-a-number",
        "whatsapp:+15551234567",
    ),
)
def test_invalid_e164_fails_validation(number: str) -> None:
    assert twilio_send.validate_e164(number) is False


def test_invalid_number_is_rejected_before_any_api_call(
    monkeypatch: pytest.MonkeyPatch,
    twilio_client: MagicMock,
    capsys: pytest.CaptureFixture[str],
) -> None:
    code = _run_main(
        monkeypatch,
        "--channel",
        "sms",
        "--to",
        "08139608051",
        "--message",
        "hello",
    )

    assert code == 1
    twilio_client.messages.create.assert_not_called()
    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err.startswith("invalid number:")


def test_mocked_auth_failure_exits_1_with_category(
    monkeypatch: pytest.MonkeyPatch,
    twilio_client: MagicMock,
    capsys: pytest.CaptureFixture[str],
) -> None:
    twilio_client.messages.create.side_effect = TwilioRestException(
        status=401,
        uri="/2010-04-01/Accounts/AC/Messages.json",
        msg="Authenticate",
        code=20003,
        method="POST",
    )

    code = _run_main(
        monkeypatch,
        "--channel",
        "sms",
        "--to",
        "+15551234567",
        "--message",
        "hello",
    )

    assert code == 1
    twilio_client.messages.create.assert_called_once()
    err = capsys.readouterr().err
    assert err.startswith("auth failure:")
    assert "code=20003" in err


def test_mocked_invalid_number_api_error_exits_1_with_category(
    monkeypatch: pytest.MonkeyPatch,
    twilio_client: MagicMock,
    capsys: pytest.CaptureFixture[str],
) -> None:
    twilio_client.messages.create.side_effect = TwilioRestException(
        status=400,
        uri="/2010-04-01/Accounts/AC/Messages.json",
        msg="Invalid 'To' Phone Number",
        code=21211,
        method="POST",
    )

    code = _run_main(
        monkeypatch,
        "--channel",
        "whatsapp",
        "--to",
        "+15551234567",
        "--message",
        "hello",
    )

    assert code == 1
    err = capsys.readouterr().err
    assert err.startswith("invalid number:")
    assert "code=21211" in err


def test_successful_mocked_send_prints_sid_and_exits_0(
    monkeypatch: pytest.MonkeyPatch,
    twilio_client: MagicMock,
    capsys: pytest.CaptureFixture[str],
) -> None:
    twilio_client.messages.create.return_value = MagicMock(sid="SM123abc456def")

    code = _run_main(
        monkeypatch,
        "--channel",
        "sms",
        "--to",
        "+15551234567",
        "--message",
        "hello",
    )

    assert code == 0
    captured = capsys.readouterr()
    assert captured.out.strip() == "SM123abc456def"
    assert captured.err == ""
    twilio_client.messages.create.assert_called_once_with(
        to="+15551234567",
        from_="+15557654321",
        body="hello",
    )


def test_connection_error_redacts_account_sid(
    monkeypatch: pytest.MonkeyPatch,
    twilio_client: MagicMock,
    capsys: pytest.CaptureFixture[str],
) -> None:
    twilio_client.messages.create.side_effect = requests.exceptions.ConnectionError(
        "HTTPSConnectionPool(host='api.twilio.com', port=443): Max retries exceeded "
        "with url: /2010-04-01/Accounts/ACaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa/Messages.json"
    )

    code = _run_main(
        monkeypatch,
        "--channel",
        "sms",
        "--to",
        "+15551234567",
        "--message",
        "hello",
    )

    assert code == 1
    err = capsys.readouterr().err
    assert err.startswith("network timeout:")
    assert "ACaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa" not in err
    assert "AC[REDACTED]" in err
