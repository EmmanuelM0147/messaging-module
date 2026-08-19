# twilio_send

CLI that sends one WhatsApp or SMS message through Twilio.

## Prerequisites

- Python 3.11+
- A Twilio account, Account SID, and Auth Token
- `TWILIO_SMS_FROM`: an SMS-capable Twilio number
- `TWILIO_WHATSAPP_FROM`: the WhatsApp sandbox or a WhatsApp-enabled sender
- Recipients in E.164 (`+[country][subscriber]`, 8-15 digits after `+`)

Install:

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

The Twilio SDK is pinned to major version 9 (`twilio>=9.4.0,<10`).

## Credentials

WhatsApp sandbox and SMS are different sender identities. Do not put the same number in both FROM variables.

| Variable | Used for |
|---|---|
| `TWILIO_ACCOUNT_SID` | Account SID |
| `TWILIO_AUTH_TOKEN` | Auth Token |
| `TWILIO_WHATSAPP_FROM` | WhatsApp From (sandbox or business) |
| `TWILIO_SMS_FROM` | SMS From |

Local default is a `.env` file:

```bash
copy .env.example .env
```

```
TWILIO_ACCOUNT_SID=ACxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
TWILIO_AUTH_TOKEN=your_auth_token
TWILIO_WHATSAPP_FROM=whatsapp:+14155238886
TWILIO_SMS_FROM=+15551234567
```

The CLI loads `.env` from the current directory, `twilio-messaging-cli/.env`, and the repo-root `../.env`. Variables already set in the OS environment are left alone.

PowerShell (current session only):

```powershell
$env:TWILIO_ACCOUNT_SID = "ACxxxxxxxx"
$env:TWILIO_AUTH_TOKEN = "your_auth_token"
$env:TWILIO_WHATSAPP_FROM = "whatsapp:+14155238886"
$env:TWILIO_SMS_FROM = "+15551234567"
```

## Example commands

SMS:

```bash
python twilio_send.py --channel sms --to +15551234567 --message "Hello from SMS"
```

WhatsApp:

```bash
python twilio_send.py --channel whatsapp --to +15551234567 --message "Hello from WhatsApp"
```

`--to` is checked as E.164 before any Twilio request. For WhatsApp, `whatsapp:` is added to From and To when it is not already there.

## WhatsApp sandbox

The recipient must already have sent the join code (for example `join <your-sandbox-keyword>`) to the sandbox number. Until they opt in, Twilio rejects the WhatsApp send even when `--to` is valid E.164.

## Output

| Result | stdout / stderr | exit code |
|---|---|---|
| Sent | message SID on stdout | 0 |
| Failed | categorized error on stderr | 1 |
| Bad CLI usage | argparse help on stderr | 2 |

Failure categories:

- `invalid number` - local E.164 check failed, or Twilio rejected the number
- `auth failure` - bad Account SID or Auth Token
- `network timeout` - connect/read timeout or connection error (not retried; a second create can send a second message)
- `unknown Twilio API error` - any other Twilio or unexpected error
- `error: TWILIO_SMS_FROM is not set` - missing config (variable name changes)
