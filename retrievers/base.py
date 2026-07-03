import json
import re
from abc import ABC, abstractmethod
from pathlib import Path

from config import SKILL_LIBRARY_PATH


class BaseRetriever(ABC):
    def __init__(self, library_path: str | Path = SKILL_LIBRARY_PATH) -> None:
        self.library_path = Path(library_path)
        self.skills = load_skill_library(self.library_path)

    @abstractmethod
    def retrieve(self, query: str, top_k: int = 5) -> list[dict]:
        raise NotImplementedError


def load_skill_library(path: str | Path = SKILL_LIBRARY_PATH) -> list[dict]:
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"Skill library was not found: {path}")
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, list):
        raise ValueError("Skill library must be a JSON list.")
    return data


def skill_to_document(skill: dict) -> str:
    examples = skill.get("examples", [])
    rendered_examples = " ".join(
        f"{example.get('input', '')} {example.get('output', '')}"
        for example in examples
        if isinstance(example, dict)
    )
    fields = [
        skill.get("name", ""),
        skill.get("description", ""),
        " ".join(skill.get("keywords", [])),
        rendered_examples,
    ]
    return " ".join(fields)


def tokenize(text: str) -> list[str]:
    lowered = str(text).lower()
    return re.findall(r"[a-z0-9_]+|[\u4e00-\u9fff]", lowered)
