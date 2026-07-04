import json
from pathlib import Path

import pandas as pd
import streamlit as st

from agents.react_agent import MinimalSkillAgent
from config import MODEL_PATH, RESULTS_DIR
from model.llama_wrapper import LocalLlamaModel
from retrievers.bm25_retriever import BM25SkillRetriever
from retrievers.embedding_retriever import EmbeddingSkillRetriever
from retrievers.full_prompt_retriever import FullPromptRetriever


PROJECT_ROOT = Path(__file__).resolve().parents[1]
BENCHMARK_PATH = PROJECT_ROOT / "data" / "skillbench_mini.json"
SKILL_LIBRARY_PATH = PROJECT_ROOT / "data" / "skill_library.json"


def apply_page_style() -> None:
    st.markdown(
        """
        <style>
        .block-container {
            padding-top: 1.4rem;
            padding-bottom: 2.5rem;
            max-width: 1440px;
        }
        [data-testid="stSidebar"] {
            background: #f8fafc;
            border-right: 1px solid #e5e7eb;
        }
        [data-testid="stSidebar"] .stButton > button {
            width: 100%;
            min-height: 42px;
            justify-content: flex-start;
            border-radius: 8px;
            border: 1px solid #e5e7eb;
            background: #ffffff;
            color: #334155;
            font-weight: 600;
            text-align: left;
            white-space: normal;
        }
        [data-testid="stSidebar"] .stButton > button:hover {
            border-color: #bfdbfe;
            background: #eff6ff;
            color: #1d4ed8;
        }
        [data-testid="stSidebar"] .stButton > button[kind="primary"],
        [data-testid="stSidebar"] [data-testid="stBaseButton-primary"] {
            border-color: #93c5fd;
            background: #eff6ff;
            color: #1d4ed8;
            box-shadow: inset 3px 0 0 #2563eb;
        }
        .section-card {
            border: 1px solid #e5e7eb;
            border-radius: 8px;
            padding: 16px;
            background: #ffffff;
        }
        .status-pill {
            display: inline-block;
            padding: 4px 10px;
            border-radius: 999px;
            border: 1px solid #bfdbfe;
            background: #eff6ff;
            color: #1d4ed8;
            font-size: 12px;
            font-weight: 600;
        }
        .pipeline {
            display: flex;
            flex-wrap: wrap;
            gap: 8px;
            align-items: center;
            margin: 12px 0 4px;
        }
        .pipeline-step {
            border: 1px solid #dbe4ef;
            border-radius: 8px;
            padding: 10px 12px;
            background: #ffffff;
            color: #0f172a;
            font-weight: 600;
            font-size: 13px;
        }
        .pipeline-arrow {
            color: #64748b;
            font-weight: 700;
        }
        .chat-row {
            border: 1px solid #e5e7eb;
            border-radius: 8px;
            padding: 8px 10px;
            margin-bottom: 6px;
            background: #ffffff;
        }
        .chat-row-active {
            border-color: #93c5fd;
            background: #eff6ff;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


@st.cache_data(show_spinner=False)
def load_benchmark() -> list[dict]:
    return json.loads(BENCHMARK_PATH.read_text(encoding="utf-8"))


@st.cache_data(show_spinner=False)
def load_skill_library() -> list[dict]:
    return json.loads(SKILL_LIBRARY_PATH.read_text(encoding="utf-8"))


def list_jsonl_files() -> list[Path]:
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    return sorted(RESULTS_DIR.glob("*.jsonl"), key=lambda path: path.stat().st_mtime, reverse=True)


def read_jsonl(path: str | Path) -> list[dict]:
    rows = []
    with Path(path).open("r", encoding="utf-8") as file:
        for line in file:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def dataframe_from_records(records: list[dict], columns: list[str] | None = None) -> pd.DataFrame:
    if not records:
        return pd.DataFrame(columns=columns or [])
    frame = pd.DataFrame(records)
    return frame[columns] if columns else frame


def model_file_status() -> tuple[bool, str]:
    path = Path(MODEL_PATH)
    if path.exists():
        size_gb = path.stat().st_size / (1024**3)
        return True, f"模型文件存在：{path.name} ({size_gb:.2f} GB)"
    return False, f"模型文件不存在：{path}"


@st.cache_resource(show_spinner=False)
def get_model() -> LocalLlamaModel:
    return LocalLlamaModel()


@st.cache_resource(show_spinner=False)
def get_retriever(name: str):
    if name == "full":
        return FullPromptRetriever()
    if name == "bm25":
        return BM25SkillRetriever()
    if name == "embedding":
        return EmbeddingSkillRetriever()
    raise ValueError(f"Unknown retriever: {name}")


def build_agent(retriever_name: str, top_k: int, max_steps: int) -> MinimalSkillAgent:
    return MinimalSkillAgent(
        model=get_model(),
        retriever=get_retriever(retriever_name),
        max_steps=max_steps,
        top_k=top_k,
    )


def method_from_label(label: str) -> str:
    return {
        "Full": "full",
        "BM25": "bm25",
        "Embedding": "embedding",
    }.get(label, label.lower())


def format_score(value) -> str:
    try:
        return f"{float(value):.4f}"
    except (TypeError, ValueError):
        return ""


def compact_skill_rows(skills: list[dict]) -> list[dict]:
    return [
        {
            "name": skill.get("name", ""),
            "score": format_score(skill.get("score", "")),
            "description": skill.get("description", ""),
        }
        for skill in skills
    ]


def render_pipeline() -> None:
    steps = [
        "任务",
        "Skill 检索",
        "候选 Skills",
        "本地 Llama2",
        "Skill 调用",
        "Observation",
        "最终答案",
        "Evaluation",
    ]
    html = ['<div class="pipeline">']
    for index, step in enumerate(steps):
        html.append(f'<span class="pipeline-step">{step}</span>')
        if index < len(steps) - 1:
            html.append('<span class="pipeline-arrow">-&gt;</span>')
    html.append("</div>")
    st.markdown("".join(html), unsafe_allow_html=True)
