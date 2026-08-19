# messaging-module

Python CLI for sending a WhatsApp or SMS message through Twilio.

The tool lives in [`twilio-messaging-cli/`](twilio-messaging-cli/). Full setup, credentials, and examples: [`twilio-messaging-cli/README.md`](twilio-messaging-cli/README.md).

```bash
cd twilio-messaging-cli
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
python twilio_send.py --channel sms --to +15551234567 --message "Hello"
```

Do not commit `.env`. Copy `twilio-messaging-cli/.env.example` and fill in the four `TWILIO_*` variables.

GitHub Actions runs the mocked pytest suite on every push. No Twilio credentials are used in CI.
