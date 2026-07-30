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


def build_recent_history(session: dict, max_turns: int = 6, max_chars: int = 3000) -> str:
    messages = session.get("messages", [])
    max_messages = max(0, max_turns) * 2
    if max_messages:
        messages = messages[-max_messages:]

    rendered = []
    for message in messages:
        role = message.get("role", "")
        if role == "user":
            label = "User"
        elif role == "assistant":
            label = "Assistant"
        else:
            continue

        content = _clean_history_content(str(message.get("content", "")), role)
        content = " ".join(content.split())
        if content:
            rendered.append(f"{label}: {content}")

    if not rendered:
        return "None"

    selected = []
    total_chars = 0
    for line in reversed(rendered):
        line_size = len(line) + 1
        if selected and total_chars + line_size > max_chars:
            break
        if not selected and line_size > max_chars:
            line = line[-max_chars:]
            line_size = len(line)
        selected.append(line)
        total_chars += line_size

    return "\n".join(reversed(selected))


def _clean_history_content(content: str, role: str) -> str:
    if role != "assistant":
        return content

    prefixes = [
        "Based on your conversation history,",
        "Based on the conversation history,",
        "From the conversation history,",
        "Based on our conversation,",
        "根据对话历史，",
        "根据对话历史,",
        "根据我们的对话，",
        "根据我们的对话,",
    ]
    cleaned = content.strip()
    changed = True
    while changed:
        changed = False
        for prefix in prefixes:
            if cleaned.lower().startswith(prefix.lower()):
                cleaned = cleaned[len(prefix):].lstrip()
                changed = True
    return cleaned
