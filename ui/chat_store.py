import json
import mimetypes
import base64
import re
from datetime import datetime
from pathlib import Path
from uuid import uuid4

from config import CHAT_IMAGE_DIR, RESULTS_DIR


CHAT_DIR = RESULTS_DIR / "chat_sessions"
TITLE_LIMIT = 34
ALLOWED_IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp"}
MAX_VISION_IMAGE_EDGE = 768


def ensure_chat_dir() -> None:
    CHAT_DIR.mkdir(parents=True, exist_ok=True)


def ensure_chat_image_dir(session_id: str) -> Path:
    directory = CHAT_IMAGE_DIR / session_id
    directory.mkdir(parents=True, exist_ok=True)
    return directory


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


def append_message(
    session: dict,
    role: str,
    content: str,
    debug: dict | None = None,
    attachments: list[dict] | None = None,
) -> None:
    message = {
        "role": role,
        "content": str(content),
        "created_at": now_iso(),
    }
    if attachments:
        message["attachments"] = attachments
    if debug:
        message["debug"] = debug
    session.setdefault("messages", []).append(message)
    if role == "user" and session.get("title") == "新对话":
        session["title"] = truncate_title(content or "图片问题")


def save_chat_image(session_id: str, uploaded_file) -> dict:
    """Persist one Streamlit UploadedFile and return lightweight metadata."""
    image_dir = ensure_chat_image_dir(session_id)
    original_name = getattr(uploaded_file, "name", "") or "pasted_image"
    mime_type = getattr(uploaded_file, "type", "") or mimetypes.guess_type(original_name)[0] or "image/png"
    extension = _safe_image_extension(original_name, mime_type)
    filename = f"{datetime.now().strftime('%Y%m%d_%H%M%S')}_{uuid4().hex[:8]}{extension}"
    path = image_dir / filename
    data = uploaded_file.getvalue()
    path.write_bytes(data)
    model_path = _create_model_image_copy(path)
    return {
        "type": "image",
        "name": original_name,
        "mime_type": mime_type,
        "path": str(path),
        "model_path": str(model_path),
        "size_bytes": len(data),
    }


def save_chat_image_data_url(session_id: str, data_url: str, original_name: str = "clipboard.png") -> dict:
    """Persist one pasted data URL image and return lightweight metadata."""
    if "," not in data_url:
        raise ValueError("Invalid image data URL.")
    header, encoded = data_url.split(",", 1)
    mime_type = "image/png"
    if header.startswith("data:") and ";" in header:
        mime_type = header[5:header.index(";")] or mime_type
    data = base64.b64decode(encoded)

    image_dir = ensure_chat_image_dir(session_id)
    extension = _safe_image_extension(original_name, mime_type)
    filename = f"{datetime.now().strftime('%Y%m%d_%H%M%S')}_{uuid4().hex[:8]}{extension}"
    path = image_dir / filename
    path.write_bytes(data)
    model_path = _create_model_image_copy(path)
    return {
        "type": "image",
        "name": original_name or "clipboard.png",
        "mime_type": mime_type,
        "path": str(path),
        "model_path": str(model_path),
        "size_bytes": len(data),
    }


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
        attachments = message.get("attachments", [])
        image_names = [
            str(item.get("name") or Path(str(item.get("path", ""))).name)
            for item in attachments
            if item.get("type") == "image"
        ]
        if role == "user" and image_names:
            image_note = ", ".join(image_names)
            content = f"{content} [image attached: {image_note}]".strip()
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
    cleaned = _strip_think_blocks(_strip_chat_template_tokens(content))
    if role != "assistant":
        return cleaned

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
    cleaned = cleaned.strip()
    changed = True
    while changed:
        changed = False
        for prefix in prefixes:
            if cleaned.lower().startswith(prefix.lower()):
                cleaned = cleaned[len(prefix):].lstrip()
                changed = True
    return cleaned


def _strip_chat_template_tokens(content: str) -> str:
    return content.replace("[/INST]", " ").replace("[INST]", " ")


def _strip_think_blocks(content: str) -> str:
    cleaned = re.sub(r"<think>.*?</think>", "", str(content), flags=re.IGNORECASE | re.DOTALL)
    if re.search(r"<think>", cleaned, flags=re.IGNORECASE):
        cleaned = re.split(r"<think>", cleaned, maxsplit=1, flags=re.IGNORECASE)[0]
    cleaned = re.sub(r"</?think>", "", cleaned, flags=re.IGNORECASE)
    return cleaned.strip()


def _safe_image_extension(original_name: str, mime_type: str) -> str:
    extension = Path(original_name).suffix.lower()
    if extension in ALLOWED_IMAGE_EXTENSIONS:
        return extension
    guessed = mimetypes.guess_extension(mime_type or "")
    if guessed:
        guessed = ".jpg" if guessed == ".jpe" else guessed.lower()
        if guessed in ALLOWED_IMAGE_EXTENSIONS:
            return guessed
    return ".png"


def _create_model_image_copy(source_path: Path) -> Path:
    """Create a smaller PNG for Qwen2.5-VL to avoid large screenshot failures."""
    try:
        from PIL import Image
    except ImportError:
        return source_path

    try:
        with Image.open(source_path) as image:
            image.load()
            needs_resize = max(image.size) > MAX_VISION_IMAGE_EDGE
            needs_png = source_path.suffix.lower() not in {".png", ".jpg", ".jpeg"}
            if not needs_resize and not needs_png:
                return source_path

            if needs_resize:
                scale = MAX_VISION_IMAGE_EDGE / max(image.size)
                size = (
                    max(1, int(image.size[0] * scale)),
                    max(1, int(image.size[1] * scale)),
                )
                image = image.resize(size, Image.Resampling.LANCZOS)
            if image.mode not in {"RGB", "L"}:
                image = image.convert("RGB")

            model_path = source_path.with_name(f"{source_path.stem}_model.png")
            image.save(model_path, format="PNG")
            return model_path
    except Exception:
        return source_path
