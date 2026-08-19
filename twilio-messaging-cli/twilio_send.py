#!/usr/bin/env python3
"""Send a WhatsApp or SMS message via Twilio."""

from __future__ import annotations

import argparse
import os
import re
import sys
from pathlib import Path
from typing import Literal, NoReturn

import requests
from dotenv import load_dotenv
from twilio.base.exceptions import TwilioRestException
from twilio.http.http_client import TwilioHttpClient
from twilio.rest import Client

Channel = Literal["whatsapp", "sms"]

E164_PATTERN = re.compile(r"^\+[1-9]\d{1,14}$")
REQUEST_TIMEOUT_SECONDS = 15.0

# HTTP 401 is also treated as auth; these are the Twilio codes that mean the same.
AUTH_ERROR_CODES = frozenset({20003, 20008})
# Number-specific Twilio codes so a bad From/To is not reported as a generic API error.
INVALID_NUMBER_CODES = frozenset(
    {21211, 21212, 21217, 21219, 21401, 21614, 21606, 21612, 21659, 63003}
)

_WHATSAPP_PREFIX = "whatsapp:"
_ACCOUNT_SID_RE = re.compile(r"AC[0-9a-fA-F]{32}")
_API_KEY_SID_RE = re.compile(r"SK[0-9a-fA-F]{32}")
_BASIC_AUTH_RE = re.compile(r"(?i)(basic\s+)[A-Za-z0-9+/=]+")
_AUTH_TOKEN_ASSIGN_RE = re.compile(
    r"(?i)(auth[_-]?token\s*[:=]\s*)[^\s,;]+",
)


class ConfigError(Exception):
    """Missing env vars; main() prints this and exits 1 without calling Twilio."""


class SendError(Exception):
    """Send failed; main() prints the message as-is and exits 1."""


def _redact_secrets(text: str) -> str:
    """Twilio URLs and exception text can include Account SID or Basic auth."""
    redacted = _ACCOUNT_SID_RE.sub("AC[REDACTED]", text)
    redacted = _API_KEY_SID_RE.sub("SK[REDACTED]", redacted)
    redacted = _BASIC_AUTH_RE.sub(r"\1[REDACTED]", redacted)
    redacted = _AUTH_TOKEN_ASSIGN_RE.sub(r"\1[REDACTED]", redacted)
    for env_name in ("TWILIO_AUTH_TOKEN", "TWILIO_ACCOUNT_SID"):
        secret = os.getenv(env_name, "").strip()
        if secret:
            redacted = redacted.replace(secret, "[REDACTED]")
    return redacted


def _safe_exc_text(exc: BaseException) -> str:
    return _redact_secrets(str(exc))


def _fail_send(message: str) -> NoReturn:
    # Drop the chained exception so a traceback cannot leak request URLs or headers.
    raise SendError(message) from None


def validate_e164(number: str) -> bool:
    return E164_PATTERN.fullmatch(number) is not None


def _require_env(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        raise ConfigError(f"{name} is not set")
    return value


def _with_whatsapp_prefix(number: str) -> str:
    if number.startswith(_WHATSAPP_PREFIX):
        return number
    return f"{_WHATSAPP_PREFIX}{number}"


def _format_twilio_error(exc: TwilioRestException) -> str:
    if exc.status == 401 or exc.code in AUTH_ERROR_CODES:
        category = "auth failure"
    elif exc.code in INVALID_NUMBER_CODES:
        category = "invalid number"
    else:
        category = "unknown Twilio API error"

    detail = _redact_secrets(
        (exc.msg or "").strip() or "Twilio did not include an error message"
    )
    code = exc.code if exc.code is not None else exc.status
    return f"{category}: {detail} (code={code})"


def build_client() -> Client:
    missing: list[str] = []
    account_sid = os.getenv("TWILIO_ACCOUNT_SID", "").strip()
    auth_token = os.getenv("TWILIO_AUTH_TOKEN", "").strip()
    if not account_sid:
        missing.append("TWILIO_ACCOUNT_SID")
    if not auth_token:
        missing.append("TWILIO_AUTH_TOKEN")
    if missing:
        names = " and ".join(missing)
        verb = "are" if len(missing) > 1 else "is"
        raise ConfigError(f"{names} {verb} not set")

    # max_retries=0: Messages.create is not idempotent, so a retry can double-send.
    http_client = TwilioHttpClient(
        timeout=REQUEST_TIMEOUT_SECONDS,
        max_retries=0,
    )
    return Client(account_sid, auth_token, http_client=http_client)


def send_message(channel: Channel, to: str, message: str) -> str:
    # WhatsApp sandbox and SMS are different sender identities; they cannot share FROM.
    if channel == "whatsapp":
        from_number = _with_whatsapp_prefix(_require_env("TWILIO_WHATSAPP_FROM"))
        to_address = _with_whatsapp_prefix(to)
    else:
        from_number = _require_env("TWILIO_SMS_FROM")
        to_address = to

    client = build_client()

    try:
        created = client.messages.create(
            to=to_address,
            from_=from_number,
            body=message,
        )
    except TwilioRestException as exc:
        _fail_send(_format_twilio_error(exc))
    except requests.exceptions.Timeout as exc:
        _fail_send(
            "network timeout: timed out reaching Twilio "
            f"({_safe_exc_text(exc)}). Not retrying, because a second create "
            "can send a second message"
        )
    except requests.exceptions.ConnectionError as exc:
        _fail_send(
            "network timeout: could not reach Twilio "
            f"({_safe_exc_text(exc)}). Not retrying, because a second create "
            "can send a second message"
        )
    except Exception as exc:  # noqa: BLE001
        _fail_send(f"unknown Twilio API error: {_safe_exc_text(exc)}")

    return created.sid


def _load_env() -> None:
    # CLI dir, then repo root (this project's .env lives one level up), then cwd.
    script_dir = Path(__file__).resolve().parent
    load_dotenv(script_dir / ".env")
    load_dotenv(script_dir.parent / ".env")
    load_dotenv()


def main() -> None:
    _load_env()

    parser = argparse.ArgumentParser(
        prog="twilio_send",
        description="Send a WhatsApp or SMS message via Twilio.",
    )
    parser.add_argument(
        "--channel",
        required=True,
        choices=("whatsapp", "sms"),
        help="whatsapp or sms",
    )
    parser.add_argument(
        "--to",
        required=True,
        metavar="E164",
        help="recipient in E.164, e.g. +15551234567",
    )
    parser.add_argument(
        "--message",
        required=True,
        help="message body",
    )
    args = parser.parse_args()

    if not validate_e164(args.to):
        print(
            f"invalid number: {args.to!r} is not E.164 "
            "(use +countrycode then the number, with no spaces)",
            file=sys.stderr,
        )
        sys.exit(1)

    try:
        sid = send_message(args.channel, args.to, args.message)
    except ConfigError as exc:
        print(f"error: {_redact_secrets(str(exc))}", file=sys.stderr)
        sys.exit(1)
    except SendError as exc:
        print(_redact_secrets(str(exc)), file=sys.stderr)
        sys.exit(1)
    except Exception as exc:  # noqa: BLE001
        print(
            f"unknown Twilio API error: {_safe_exc_text(exc)}",
            file=sys.stderr,
        )
        sys.exit(1)

    print(sid)
    sys.exit(0)


if __name__ == "__main__":
    main()
