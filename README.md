# Lead Reviver

**Bring cold leads back into conversation—with evidence-aware AI follow-ups.**

Lead Reviver is an AI-assisted lead-management workspace for sales teams and small businesses. It identifies leads that deserve attention, explains why they are prioritized, retrieves relevant product and sales context, and drafts respectful follow-up messages with Gemini. Messages are saved for human review; outreach is never sent automatically.

[![CI](https://github.com/Xatreus/lead-reviver-/actions/workflows/ci.yml/badge.svg)](https://github.com/Xatreus/lead-reviver-/actions/workflows/ci.yml)
[![Python](https://img.shields.io/badge/python-3.12%2B-blue)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/API-FastAPI-009688)](https://fastapi.tiangolo.com/)
[![PostgreSQL](https://img.shields.io/badge/database-PostgreSQL%20%2B%20pgvector-4169E1)](https://github.com/pgvector/pgvector)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)

## Problem and approach

Sales follow-up fails when teams have too many leads, incomplete context, and no clear next action. Lead Reviver combines deterministic prioritization with retrieval-augmented generation (RAG), helping a person choose whom to contact and draft a message grounded in approved reference material.

## Features

- Lead CRUD, search, status filtering, and CSV import/export.
- Explainable revival score based on contact recency, due dates, deal value, and pipeline stage. This is a heuristic, not a predictive conversion model.
- Gemini-powered email, SMS, and LinkedIn draft generation with configurable goal and tone.
- RAG knowledge base for approved product facts, FAQs, service details, and sales playbooks.
- PostgreSQL vector search using pgvector cosine distance; SQLite uses an in-process cosine-similarity fallback for local development.
- Saved drafts, knowledge-document management, and semantic search endpoints.
- Consent guardrails: opted-out and do-not-contact leads cannot generate drafts.
- FastAPI REST API with validation and interactive OpenAPI documentation.
- Docker Compose development environment for PostgreSQL + pgvector.

## Architecture

    Browser dashboard
           |
           v
    FastAPI REST API -----> deterministic lead scoring
           |
           v
    SQLAlchemy ORM -------> PostgreSQL / SQLite
           |
           +---- knowledge documents -> chunking -> Gemini embeddings
           |                                     |
           |                                     v
           |                              pgvector similarity search
           v
    Gemini generation <---- retrieved context + lead details
           |
           v
    Saved draft for human review (never auto-sent)

## Stack and design choices

| Area | Technology | Why it is used |
| --- | --- | --- |
| API | FastAPI + Pydantic | Validation, REST boundaries, OpenAPI docs |
| Persistence | SQLAlchemy 2.x | ORM, parameterized queries, database abstraction |
| Production DB | PostgreSQL + psycopg 3 | Reliable relational storage |
| Vector retrieval | pgvector + HNSW index | Store vectors alongside application data |
| Local DB | SQLite | Fast setup without infrastructure |
| Migrations | Alembic | Versioned, reviewable schema changes |
| AI | Official Google Gen AI SDK | Gemini text generation and embeddings |
| Quality | pytest, FastAPI TestClient, Ruff | Automated tests and lint |
| Packaging/deploy | Docker + Compose | Repeatable local PostgreSQL environment |

## Quick start: SQLite

Requirements: Python 3.12+, Git, and a Gemini API key for AI features. Lead management and scoring work without a Gemini key.

Windows PowerShell:

    git clone https://github.com/Xatreus/lead-reviver-.git
    cd lead-reviver-
    py -3.12 -m venv .venv
    .\.venv\Scripts\Activate.ps1
    python -m pip install --upgrade pip
    pip install -e ".[dev]"
    Copy-Item .env.example .env

Add your Gemini API key to .env. Keep the file private and never commit credentials. Suggested configuration:

    DATABASE_URL=sqlite:///./data/lead_reviver.db
    GEMINI_API_KEY=your_key_here
    GEMINI_MODEL=gemini-3.8-flash
    GEMINI_EMBEDDING_MODEL=gemini-embedding-2

Run the app:

    uvicorn app.main:app --reload

Dashboard: http://127.0.0.1:8000  
Interactive API docs: http://127.0.0.1:8000/docs  
Health: http://127.0.0.1:8000/health

## PostgreSQL + pgvector with Docker Compose

1. Install Docker Desktop.
2. Copy .env.example to .env and add your Gemini key.
3. Start the stack:

    docker compose up --build

Compose starts PostgreSQL with pgvector, waits for the database health check, applies the Alembic migration, and launches FastAPI. The default database password is for local development only. Set POSTGRES_PASSWORD to a strong secret before using a shared environment.

Stop the services:

    docker compose down

Delete the local database volume (destructive):

    docker compose down -v

## RAG workflow

1. POST approved reference content to /api/knowledge.
2. The service splits it into overlapping text chunks and generates Gemini embeddings.
3. Chunks and embeddings are persisted with document/source metadata.
4. Search embeds the query and ranks relevant chunks by cosine similarity.
5. Draft generation retrieves up to three chunks and passes them to Gemini as reference context.
6. The draft response includes source titles and similarity scores for review.

Example PowerShell request:

    $body = @{
      title = "Product overview"
      source = "approved/product-overview"
      content = "Describe verified product capabilities, supported use cases, and pricing rules."
    } | ConvertTo-Json

    Invoke-RestMethod -Method Post -Uri http://127.0.0.1:8000/api/knowledge -ContentType "application/json" -Body $body

Semantic search:

    Invoke-RestMethod "http://127.0.0.1:8000/api/knowledge/search?q=product%20capabilities"

Retrieved content is untrusted reference data, not instructions. Verify facts and review every draft before use. If the knowledge base is empty, drafting can still use the lead details supplied by the user.

## REST API

| Method | Endpoint | Purpose |
| --- | --- | --- |
| GET | /api/leads | List, filter, or search leads |
| POST | /api/leads | Create a lead |
| GET | /api/leads/{lead_id} | Read a lead |
| PATCH | /api/leads/{lead_id} | Update a lead |
| DELETE | /api/leads/{lead_id} | Delete a lead |
| GET | /api/metrics | Summary metrics |
| POST | /api/leads/{lead_id}/draft | Generate and save an AI draft |
| GET | /api/leads/{lead_id}/drafts | List saved drafts |
| POST | /api/leads/import | Import CSV (maximum 2 MB) |
| GET | /api/leads/export.csv | Export leads |
| POST | /api/knowledge | Index a knowledge document |
| GET | /api/knowledge | List indexed documents |
| GET | /api/knowledge/search?q=... | Semantic search |
| DELETE | /api/knowledge/{document_id} | Delete a document and its chunks |
| GET | /health | Service status |

OpenAPI JSON is available at /openapi.json. CSV requires a name column; optional fields include email, phone, company, source, status, deal_value, notes, last_contact_at, next_follow_up_at, and opted_out. Use ISO 8601 timestamps.

## Development and CI

    pip install -e ".[dev]"
    ruff check app tests migrations
    pytest

GitHub Actions runs lint and tests on Python 3.12 and 3.13. Automated tests use temporary SQLite databases and do not require paid Gemini API calls. PostgreSQL schema changes are versioned through Alembic; use alembic upgrade head to apply migrations.

## Security and limitations

- Generated messages are drafts only. There is no automatic email, SMS, or social-message delivery.
- Opted-out and do-not-contact leads are blocked from draft generation.
- API keys are loaded from environment variables; do not commit secrets.
- Retrieved text may be stale, inaccurate, or adversarial. Verify claims before using them.
- Only index customer/company information you have permission to process. Review consent, data-retention, and marketing requirements before using real lead data.
- Authentication, authorization, tenant isolation, rate limiting, and CSRF protections are not implemented. Keep this demo on localhost or a trusted development network; do not expose it publicly as-is.
- Before a real multi-user deployment, add authentication and tenant-scoped access, audit logs, request limits, structured observability, backups and restore tests, managed secret storage, and a security review.
- Use Alembic for schema evolution; create_all is only a convenient local bootstrap, not a production migration strategy.

## Roadmap

- [x] FastAPI REST API and browser dashboard
- [x] SQLite development mode and PostgreSQL/pgvector storage path
- [x] Initial Alembic schema migration
- [x] Gemini drafts and retrieval-grounded context
- [x] CSV workflows and deterministic lead prioritization
- [x] Automated lint and tests
- [ ] Authentication, authorization, and tenant isolation
- [ ] Background jobs, retries, and follow-up scheduling
- [ ] CRM/email integrations with explicit user-approved delivery
- [ ] Production observability, backup/restore validation, and load testing

## License

MIT. See LICENSE.
