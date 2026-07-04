import json
from datetime import datetime
from pathlib import Path
from uuid import uuid4

from config import RESULTS_DIR


CHAT_DIR = RESULTS_DIR / "chat_sessions"
TITLE_LIMIT = 34


def ensure_chat_dir() -> None:
    CHAT_DIR.mkdir(parents=True, exist_ok=True)


def now_iso() -> str:
    return datetime.now().isoformat(timespec="seconds")


def truncate_title(text: str, limit: int = TITLE_LIMIT) -> str:
    normalized = " ".join(str(text).split())
    if not normalized:
        return "新对话"
    return normalized if len(normalized) <= limit else f"{normalized[:limit]}..."


def session_path(session_id: str) -> Path:
    return CHAT_DIR / f"{session_id}.json"


def create_session() -> dict:
    ensure_chat_dir()
    created_at = now_iso()
    session = {
        "id": f"{datetime.now().strftime('%Y%m%d_%H%M%S')}_{uuid4().hex[:8]}",
        "title": "新对话",
        "created_at": created_at,
        "updated_at": created_at,
        "mode": "使用 Skill Agent",
        "retriever": "bm25",
        "messages": [],
    }
    save_session(session)
    return session


def list_sessions() -> list[dict]:
    ensure_chat_dir()
    sessions = []
    for path in CHAT_DIR.glob("*.json"):
        try:
            sessions.append(json.loads(path.read_text(encoding="utf-8")))
        except (OSError, json.JSONDecodeError):
            continue
    return sorted(sessions, key=lambda item: item.get("updated_at", ""), reverse=True)


def load_session(session_id: str) -> dict | None:
    path = session_path(session_id)
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def save_session(session: dict) -> None:
    ensure_chat_dir()
    session["updated_at"] = now_iso()
    session_path(session["id"]).write_text(
        json.dumps(session, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def append_message(session: dict, role: str, content: str, debug: dict | None = None) -> None:
    message = {
        "role": role,
        "content": str(content),
        "created_at": now_iso(),
    }
    if debug:
        message["debug"] = debug
    session.setdefault("messages", []).append(message)
    if role == "user" and session.get("title") == "新对话":
        session["title"] = truncate_title(content)

