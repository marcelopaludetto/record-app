import sqlite3
import json
from datetime import datetime
from pathlib import Path
from config import DB_PATH
from storage.models import Meeting, Topic, Bullet, NextStep


def _connect():
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    with _connect() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS meetings (
                id               INTEGER PRIMARY KEY AUTOINCREMENT,
                title            TEXT NOT NULL,
                started_at       TEXT NOT NULL,
                ended_at         TEXT,
                status           TEXT DEFAULT 'recording',
                audio_path       TEXT,
                transcript_path  TEXT,
                output_md_path   TEXT,
                transcript_text  TEXT,
                topics           TEXT,
                next_steps       TEXT,
                whisper_model    TEXT,
                ollama_model     TEXT,
                error_message    TEXT,
                tipo_agenda      TEXT,
                temas            TEXT,
                tldr             TEXT,
                created_at       TEXT DEFAULT (datetime('now'))
            )
        """)
        # Migração: adiciona colunas novas se o banco já existia
        existing = {r[1] for r in conn.execute("PRAGMA table_info(meetings)").fetchall()}
        for col, typedef in [
            ("tipo_agenda", "TEXT"),
            ("temas",       "TEXT"),
            ("tldr",        "TEXT"),
        ]:
            if col not in existing:
                conn.execute(f"ALTER TABLE meetings ADD COLUMN {col} {typedef}")
        conn.commit()


def save_meeting(meeting: Meeting) -> int:
    with _connect() as conn:
        cur = conn.execute("""
            INSERT INTO meetings
            (title, started_at, ended_at, status, audio_path, transcript_path,
             output_md_path, transcript_text, topics, next_steps,
             whisper_model, ollama_model, error_message,
             tipo_agenda, temas, tldr)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        """, (
            meeting.title,
            meeting.started_at.isoformat(),
            meeting.ended_at.isoformat() if meeting.ended_at else None,
            meeting.status,
            str(meeting.audio_path) if meeting.audio_path else None,
            str(meeting.transcript_path) if meeting.transcript_path else None,
            str(meeting.output_md_path) if meeting.output_md_path else None,
            meeting.transcript_text,
            _topics_to_json(meeting.topics),
            _next_steps_to_json(meeting.next_steps),
            meeting.whisper_model,
            meeting.ollama_model,
            meeting.error_message,
            meeting.tipo_agenda,
            json.dumps(meeting.temas, ensure_ascii=False),
            json.dumps(meeting.tldr, ensure_ascii=False),
        ))
        conn.commit()
        return cur.lastrowid


def update_meeting(meeting: Meeting):
    if meeting.id is None:
        raise ValueError("Cannot update meeting without id")
    with _connect() as conn:
        conn.execute("""
            UPDATE meetings SET
                title=?, ended_at=?, status=?, audio_path=?,
                transcript_path=?, output_md_path=?, transcript_text=?,
                topics=?, next_steps=?,
                whisper_model=?, ollama_model=?, error_message=?
            WHERE id=?
        """, (
            meeting.title,
            meeting.ended_at.isoformat() if meeting.ended_at else None,
            meeting.status,
            str(meeting.audio_path) if meeting.audio_path else None,
            str(meeting.transcript_path) if meeting.transcript_path else None,
            str(meeting.output_md_path) if meeting.output_md_path else None,
            meeting.transcript_text,
            _topics_to_json(meeting.topics),
            _next_steps_to_json(meeting.next_steps),
            meeting.whisper_model,
            meeting.ollama_model,
            meeting.error_message,
            meeting.id,
        ))
        conn.commit()


def list_active_meetings() -> list[Meeting]:
    """Retorna apenas reuniões em pipeline (não concluídas)."""
    with _connect() as conn:
        rows = conn.execute(
            "SELECT * FROM meetings WHERE status != 'done' ORDER BY started_at DESC"
        ).fetchall()
    return [_row_to_meeting(r) for r in rows]


def delete_meeting(meeting_id: int) -> None:
    with _connect() as conn:
        conn.execute("DELETE FROM meetings WHERE id=?", (meeting_id,))
        conn.commit()


def list_meetings(limit: int = 100) -> list[Meeting]:
    with _connect() as conn:
        rows = conn.execute(
            "SELECT * FROM meetings ORDER BY started_at DESC LIMIT ?", (limit,)
        ).fetchall()
    return [_row_to_meeting(r) for r in rows]


def get_meeting(meeting_id: int) -> Meeting | None:
    with _connect() as conn:
        row = conn.execute("SELECT * FROM meetings WHERE id=?", (meeting_id,)).fetchone()
    return _row_to_meeting(row) if row else None


# ------------------------------------------------------------------
# Serialização
# ------------------------------------------------------------------

def _topics_to_json(topics: list[Topic]) -> str:
    data = []
    for t in topics:
        data.append({
            "title": t.title,
            "bullets": [
                {"text": b.text, "sub_bullets": b.sub_bullets}
                for b in t.bullets
            ],
        })
    return json.dumps(data, ensure_ascii=False)


def _next_steps_to_json(steps: list[NextStep]) -> str:
    return json.dumps(
        [{"action": s.action} for s in steps],
        ensure_ascii=False,
    )


def _row_to_meeting(row: sqlite3.Row) -> Meeting:
    def _dt(v):
        return datetime.fromisoformat(v) if v else None

    def _json(v):
        try:
            return json.loads(v) if v else []
        except Exception:
            return []

    topics_raw = _json(row["topics"])
    topics = [
        Topic(
            title=t.get("title", ""),
            bullets=[
                Bullet(
                    text=b.get("text", ""),
                    sub_bullets=b.get("sub_bullets", []),
                )
                for b in t.get("bullets", [])
            ],
        )
        for t in topics_raw
    ]

    steps_raw = _json(row["next_steps"])
    next_steps = [
        NextStep(action=s.get("action", ""))
        for s in steps_raw
    ]

    m = Meeting(title=row["title"])
    m.id = row["id"]
    m.started_at = _dt(row["started_at"])
    m.ended_at = _dt(row["ended_at"])
    m.status = row["status"]
    m.audio_path = Path(row["audio_path"]) if row["audio_path"] else None
    m.transcript_path = Path(row["transcript_path"]) if row["transcript_path"] else None
    m.output_md_path = Path(row["output_md_path"]) if row["output_md_path"] else None
    m.transcript_text = row["transcript_text"] or ""
    m.topics = topics
    m.next_steps = next_steps
    m.whisper_model = row["whisper_model"] or ""
    m.ollama_model = row["ollama_model"] or ""
    m.error_message = row["error_message"] or ""
    m.tipo_agenda = row["tipo_agenda"] or ""
    m.temas = _json(row["temas"])
    m.tldr = _json(row["tldr"])
    return m
