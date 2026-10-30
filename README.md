# Lead Reviver

**Turn forgotten leads into conversations again.**

Lead Reviver is an AI-assisted follow-up workspace for salespeople and small teams who lose deals because leads go cold, follow-ups slip, or the next message is hard to write. It stores leads, prioritizes who to contact, and uses Google's Gemini API to draft personalized revival messages.

## MVP capabilities

- Create, view, update, and delete leads.
- Track status, source, deal value, last contact, and follow-up date.
- Rank leads with an explainable, deterministic revival score.
- Generate personalized follow-up drafts with Gemini.
- Import and export leads as CSV.
- Review and copy drafts before sending. **The MVP never sends messages automatically.**
- Run locally with SQLite; no paid database required.

## Architecture

- API: FastAPI + Pydantic
- Storage: SQLite
- AI: Official Google Gen AI Python SDK (`google-genai`) and Gemini Interactions API
- UI: Responsive HTML/CSS/JavaScript served by FastAPI
- Tests: pytest + FastAPI TestClient

AI drafts messages; application code controls persistence, lead scoring, validation, and follow-up state. Important business rules stay deterministic and auditable.

## Requirements

- Python 3.12+
- A Gemini API key from Google AI Studio (optional for non-AI features)

## Setup (Windows PowerShell)

```powershell
git clone https://github.com/Xatreus/lead-reviver-.git
cd lead-reviver-
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -e ".[dev]"
Copy-Item .env.example .env
```

Add your key to `.env`:

```dotenv
GEMINI_API_KEY=your_key_here
GEMINI_MODEL=gemini-4-argon
DATABASE_PATH=./data/lead_reviver.db
```

The model name is configurable; use a model enabled for your Gemini API key. Keep `.env` private and never commit API keys.

Start the app:

```powershell
uvicorn app.main:app --reload
```

Open http://127.0.0.1:8000. API docs: http://127.0.0.1:8000/docs.

## CSV import format

Required column: `name`. Optional columns: `email, phone, company, source, status, deal_value, notes, last_contact_at, next_follow_up_at, opted_out`.

Dates should be ISO 8601 values such as `2026-10-25` or `2026-10-25T15:30:00+05:30`. Unknown columns are ignored.

## Safety and limitations

- Drafts are suggestions, not verified facts. Review before using.
- No automatic email/SMS/WhatsApp delivery, CRM sync, or background scheduler yet.
- Respect consent, opt-outs, local marketing rules, and channel-specific policies. Never contact a lead who opted out.
- This local MVP has no user authentication. Do not expose it to the public internet or use it for multiple users until authentication and authorization are added.
- SQLite is for local development and small single-instance usage. Production needs migrations, backups, authentication, observability, and a managed database.

## Development

```powershell
pip install -e ".[dev]"
ruff check app tests
pytest
```

## Roadmap

1. Validate local workflow and Gemini integration.
2. Add follow-up task queue and reliable scheduler.
3. Add explicit Gmail/Calendar/CRM integrations with user-approved sending and opt-out handling.
4. Add authentication, tenant isolation, PostgreSQL, migrations, audit logs, and deployment automation.
