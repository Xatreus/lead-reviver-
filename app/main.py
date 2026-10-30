import csv
import io
import os
import sqlite3
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from pathlib import Path
from typing import Annotated, Literal

from dotenv import load_dotenv
from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.responses import HTMLResponse, StreamingResponse
from pydantic import BaseModel, ConfigDict, Field

from app.rules import revival_score

load_dotenv()
DATABASE_PATH = os.getenv("DATABASE_PATH", "./data/lead_reviver.db")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "").strip()
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-3.8-flash").strip()
LeadStatus = Literal["new", "contacted", "engaged", "proposal", "negotiation", "won", "lost", "unqualified", "do_not_contact"]


def connect_db():
    path = Path(DATABASE_PATH)
    if str(path) != ":memory:":
        path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DATABASE_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db():
    with connect_db() as conn:
        conn.execute("""CREATE TABLE IF NOT EXISTS leads (
            id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL, email TEXT, phone TEXT,
            company TEXT, source TEXT, status TEXT NOT NULL DEFAULT 'new',
            deal_value REAL NOT NULL DEFAULT 0, notes TEXT NOT NULL DEFAULT '',
            last_contact_at TEXT, next_follow_up_at TEXT, opted_out INTEGER NOT NULL DEFAULT 0,
            created_at TEXT NOT NULL, updated_at TEXT NOT NULL)""")
        conn.execute("""CREATE TABLE IF NOT EXISTS drafts (
            id INTEGER PRIMARY KEY AUTOINCREMENT, lead_id INTEGER NOT NULL REFERENCES leads(id) ON DELETE CASCADE,
            channel TEXT NOT NULL, subject TEXT NOT NULL DEFAULT '', body TEXT NOT NULL, created_at TEXT NOT NULL)""")


@asynccontextmanager
async def lifespan(_app):
    init_db()
    yield


app = FastAPI(title="Lead Reviver API", version="0.1.0", description="AI-assisted lead follow-up workspace", lifespan=lifespan)


class LeadCreate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)
    name: str = Field(min_length=1, max_length=160)
    email: str | None = Field(default=None, max_length=254)
    phone: str | None = Field(default=None, max_length=40)
    company: str | None = Field(default=None, max_length=160)
    source: str | None = Field(default=None, max_length=120)
    status: LeadStatus = "new"
    deal_value: float = Field(default=0, ge=0, le=1_000_000_000)
    notes: str = Field(default="", max_length=10000)
    last_contact_at: str | None = None
    next_follow_up_at: str | None = None
    opted_out: bool = False


class LeadUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=160)
    email: str | None = Field(default=None, max_length=254)
    phone: str | None = Field(default=None, max_length=40)
    company: str | None = Field(default=None, max_length=160)
    source: str | None = Field(default=None, max_length=120)
    status: LeadStatus | None = None
    deal_value: float | None = Field(default=None, ge=0, le=1_000_000_000)
    notes: str | None = Field(default=None, max_length=10000)
    last_contact_at: str | None = None
    next_follow_up_at: str | None = None
    opted_out: bool | None = None


class DraftRequest(BaseModel):
    channel: Literal["email", "sms", "linkedin"] = "email"
    goal: str = Field(default="restart the conversation and ask if they are still interested", max_length=500)
    tone: Literal["friendly", "professional", "concise"] = "friendly"
    extra_context: str = Field(default="", max_length=3000)


def now_iso():
    return datetime.now(UTC).isoformat()


def row_to_dict(row):
    data = dict(row)
    data["opted_out"] = bool(data.get("opted_out", False))
    data["priority"] = revival_score(data)
    return data


def get_lead(lead_id):
    with connect_db() as conn:
        row = conn.execute("SELECT * FROM leads WHERE id=?", (lead_id,)).fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail="Lead not found")
    return row_to_dict(row)


def get_db_session():
    yield from get_session(DATABASE_URL)


@app.get("/", response_class=HTMLResponse)
def home():
    return (Path(__file__).parent / "static" / "index.html").read_text(encoding="utf-8")


@app.get("/health")
def health():
    return {"status": "ok", "gemini_configured": bool(GEMINI_API_KEY), "model": GEMINI_MODEL}


@app.get("/api/leads")
def list_leads(q: str | None = None, status: str | None = None):
    sql, params = "SELECT * FROM leads WHERE 1=1", []
    if q:
        sql += " AND (name LIKE ? OR company LIKE ? OR email LIKE ?)"
        pattern = f"%{q}%"
        params.extend([pattern, pattern, pattern])
    if status:
        sql += " AND status=?"
        params.append(status)
    sql += " ORDER BY created_at DESC"
    with connect_db() as conn:
        rows = conn.execute(sql, params).fetchall()
    return [row_to_dict(row) for row in rows]


@app.post("/api/leads", status_code=201)
def create_lead(payload: LeadCreate):
    stamp, values = now_iso(), payload.model_dump()
    values["opted_out"] = int(values["opted_out"])
    fields = list(values)
    with connect_db() as conn:
        cursor = conn.execute(
            f"INSERT INTO leads ({','.join(fields)},created_at,updated_at) VALUES ({','.join('?' for _ in fields)},?,?)",
            [values[f] for f in fields] + [stamp, stamp],
        )
    return get_lead(int(cursor.lastrowid))


@app.get("/api/leads/{lead_id}")
def read_lead(lead_id: int):
    return get_lead(lead_id)


@app.patch("/api/leads/{lead_id}")
def update_lead(lead_id: int, payload: LeadUpdate):
    current = get_lead(lead_id)
    changes = payload.model_dump(exclude_unset=True)
    if not changes:
        return current
    if "opted_out" in changes and changes["opted_out"] is not None:
        changes["opted_out"] = int(changes["opted_out"])
    changes["updated_at"] = now_iso()
    with connect_db() as conn:
        conn.execute("UPDATE leads SET " + ", ".join(f"{k}=?" for k in changes) + " WHERE id=?",
                     list(changes.values()) + [lead_id])
    return get_lead(lead_id)


@app.delete("/api/leads/{lead_id}", status_code=204)
def delete_lead(lead_id: int):
    get_lead(lead_id)
    with connect_db() as conn:
        conn.execute("DELETE FROM leads WHERE id=?", (lead_id,))


@app.get("/api/metrics")
def metrics():
    with connect_db() as conn:
        groups = conn.execute("SELECT status,COUNT(*) AS count,SUM(deal_value) AS value FROM leads GROUP BY status").fetchall()
        total = conn.execute("SELECT COUNT(*) FROM leads").fetchone()[0]
        stale = conn.execute("""SELECT COUNT(*) FROM leads WHERE status NOT IN ('won','unqualified','do_not_contact')
            AND (last_contact_at IS NULL OR last_contact_at<=?)""", (now_iso(),)).fetchone()[0]
    return {"total_leads": total, "stale_or_never_contacted": stale, "by_status": [dict(r) for r in groups]}


@app.post("/api/leads/{lead_id}/draft")
def draft_revival(lead_id: int, request: DraftRequest):
    lead = get_lead(lead_id)
    if lead["opted_out"] or lead["status"] == "do_not_contact":
        raise HTTPException(status_code=409, detail="Lead opted out or is marked do-not-contact.")
    if not GEMINI_API_KEY:
        raise HTTPException(status_code=503, detail="Gemini is not configured. Add GEMINI_API_KEY to .env.")
    try:
        from google import genai
        client = genai.Client(api_key=GEMINI_API_KEY)
        prompt = f"""Write one respectful, low-pressure sales follow-up to revive a lead.
Never invent previous conversations, promises, discounts, or product facts. Use supplied context only.
Ask a simple question or offer a clear next step. Return exactly:
SUBJECT: <subject or blank>
BODY:
<message>

Channel: {request.channel}
Tone: {request.tone}
Goal: {request.goal}
Name: {lead['name']}
Company: {lead.get('company') or 'Not provided'}
Source: {lead.get('source') or 'Not provided'}
Status: {lead['status']}
Last contact: {lead.get('last_contact_at') or 'Not recorded'}
Notes: {lead.get('notes') or 'No notes'}
Additional context: {request.extra_context or 'None'}"""
        response = client.interactions.create(model=GEMINI_MODEL, input=prompt)
        output = (getattr(response, "output_text", None) or "").strip()
        if not output:
            raise RuntimeError("Gemini returned an empty response")
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Gemini draft failed ({type(exc).__name__}). Check server logs and model access.") from exc
    subject, body = "", output
    if "BODY:" in output:
        header, body = output.split("BODY:", 1)
        if "SUBJECT:" in header:
            subject = header.split("SUBJECT:", 1)[1].strip()
        body = body.strip()
    stamp = now_iso()
    with connect_db() as conn:
        cursor = conn.execute("INSERT INTO drafts (lead_id,channel,subject,body,created_at) VALUES (?,?,?,?,?)",
                              (lead_id, request.channel, subject, body, stamp))
    return {"id": cursor.lastrowid, "lead_id": lead_id, "channel": request.channel, "subject": subject, "body": body, "created_at": stamp, "sent": False}


@app.get("/api/leads/{lead_id}/drafts")
def list_drafts(lead_id: int):
    get_lead(lead_id)
    with connect_db() as conn:
        rows = conn.execute("SELECT * FROM drafts WHERE lead_id=? ORDER BY created_at DESC", (lead_id,)).fetchall()
    return [dict(row) for row in rows]


@app.post("/api/leads/import")
async def import_csv(file: Annotated[UploadFile, File()]):
    if not file.filename or not file.filename.lower().endswith(".csv"):
        raise HTTPException(status_code=400, detail="Upload a .csv file.")
    raw = await file.read()
    if len(raw) > 2_000_000:
        raise HTTPException(status_code=413, detail="CSV must be 2 MB or smaller.")
    try:
        reader = csv.DictReader(io.StringIO(raw.decode("utf-8-sig")))
        if not reader.fieldnames or "name" not in {h.strip().lower() for h in reader.fieldnames}:
            raise HTTPException(status_code=400, detail="CSV must include a name column.")
        count = 0
        with connect_db() as conn:
            for source_row in reader:
                row = {str(k).strip().lower(): (v or "").strip() for k, v in source_row.items() if k}
                if not row.get("name"):
                    continue
                valid_statuses = {"new","contacted","engaged","proposal","negotiation","won","lost","unqualified","do_not_contact"}
                status = row.get("status") if row.get("status") in valid_statuses else "new"
                try:
                    value = max(0.0, float(row.get("deal_value") or 0))
                except ValueError:
                    value = 0.0
                stamp = now_iso()
                conn.execute("""INSERT INTO leads (name,email,phone,company,source,status,deal_value,notes,last_contact_at,next_follow_up_at,opted_out,created_at,updated_at)
                    VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                    (row["name"][:160], row.get("email"), row.get("phone"), row.get("company"), row.get("source"),
                     status, value, row.get("notes","")[:10000], row.get("last_contact_at") or None,
                     row.get("next_follow_up_at") or None, int(row.get("opted_out","").lower() in {"true","1","yes"}), stamp, stamp))
                count += 1
        return {"imported": count}
    except UnicodeDecodeError as exc:
        raise HTTPException(status_code=400, detail="CSV must be UTF-8 encoded.") from exc


@app.get("/api/leads/export.csv")
def export_csv():
    with connect_db() as conn:
        rows = conn.execute("SELECT * FROM leads ORDER BY created_at DESC").fetchall()
    output = io.StringIO()
    columns = ["id","name","email","phone","company","source","status","deal_value","notes","last_contact_at","next_follow_up_at","opted_out","created_at","updated_at"]
    writer = csv.DictWriter(output, fieldnames=columns)
    writer.writeheader()
    writer.writerows([dict(row) for row in rows])
    return StreamingResponse(iter([output.getvalue()]), media_type="text/csv",
        headers={"Content-Disposition": 'attachment; filename="lead-reviver-leads.csv"'})
