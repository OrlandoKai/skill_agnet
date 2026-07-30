import argparse
import json
from datetime import datetime
from pathlib import Path

from agents.enhanced_agent import EnhancedSkillAgent
from agents.enhanced_agent_v2 import ABLATION_CHOICES, EnhancedSkillAgentV2
from agents.enhanced_agent_v3 import EnhancedSkillAgentV3
from agents.enhanced_agent_v4 import EnhancedSkillAgentV4
from agents.enhanced_agent_v5 import EnhancedSkillAgentV5
from agents.react_agent import MinimalSkillAgent
from config import DEFAULT_TOP_K, MODEL_PATH, RESULTS_DIR
from eval.skillbench_eval import evaluate_skillbench_result
from model.llama_wrapper import LocalLlamaModel
from retrievers.bm25_retriever import BM25SkillRetriever
from retrievers.embedding_retriever import EmbeddingSkillRetriever
from retrievers.full_prompt_retriever import FullPromptRetriever


PROJECT_ROOT = Path(__file__).resolve().parent
DEFAULT_BENCHMARK = PROJECT_ROOT / "data" / "skillbench_mini.json"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run SkillBench-Mini baselines.")
    parser.add_argument("--task", help="Optional ad-hoc single task instruction.")
    parser.add_argument(
        "--benchmark",
        default=str(DEFAULT_BENCHMARK),
        help="Benchmark JSON file. Ignored when --task is provided.",
    )
    parser.add_argument(
        "--retriever",
        choices=["full", "bm25", "embedding"],
        default="bm25",
        help="Skill retriever baseline.",
    )
    parser.add_argument(
        "--agent",
        choices=[
            "baseline",
            "enhanced",
            "enhanced_v2",
            "enhanced_v3",
            "enhanced_v4",
            "enhanced_v5",
        ],
        default="baseline",
        help="Agent policy. baseline preserves the original MinimalSkillAgent.",
    )
    parser.add_argument(
        "--ablation",
        choices=sorted(ABLATION_CHOICES),
        default="none",
        help="Enhanced V2 ablation switch. Ignored by baseline and enhanced agents.",
    )
    parser.add_argument("--top_k", "--top-k", dest="top_k", type=int, default=DEFAULT_TOP_K)
    parser.add_argument("--max_steps", "--max-steps", dest="max_steps", type=int, default=2)
    parser.add_argument("--max_tasks", "--max-tasks", dest="max_tasks", type=int, default=10)
    parser.add_argument(
        "--output",
        help="Output JSONL path. Defaults to results/run_<agent>_<retriever>_<timestamp>.jsonl.",
    )
    parser.add_argument(
        "--model_path",
        "--model-path",
        dest="model_path",
        default=MODEL_PATH,
        help="Local GGUF model path. Defaults to config.MODEL_PATH.",
    )
    return parser.parse_args()


def build_retriever(name: str):
    if name == "full":
        return FullPromptRetriever()
    if name == "bm25":
        return BM25SkillRetriever()
    if name == "embedding":
        return EmbeddingSkillRetriever()
    raise ValueError(f"Unknown retriever: {name}")


def load_tasks(args: argparse.Namespace) -> list[dict]:
    if args.task:
        return [
            {
                "task_id": "ad_hoc",
                "instruction": args.task,
                "gold_skills": [],
                "expected_answer": "",
                "task_type": "ad_hoc",
                "notes": "Ad-hoc command line task.",
            }
        ]

    tasks = json.loads(Path(args.benchmark).read_text(encoding="utf-8"))
    if args.max_tasks and args.max_tasks > 0:
        return tasks[: args.max_tasks]
    return tasks


def default_output_path(agent_name: str, retriever_name: str, ablation: str = "none") -> Path:
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    suffix = f"_{ablation}" if ablation and ablation != "none" else ""
    return RESULTS_DIR / f"run_{agent_name}_{retriever_name}{suffix}_{timestamp}.jsonl"


def build_agent(
    agent_name: str,
    model,
    retriever,
    max_steps: int,
    top_k: int,
    ablation: str = "none",
):
    if agent_name == "baseline":
        return MinimalSkillAgent(
            model=model,
            retriever=retriever,
            max_steps=max_steps,
            top_k=top_k,
        )
    if agent_name == "enhanced":
        return EnhancedSkillAgent(
            model=model,
            retriever=retriever,
            max_steps=max_steps,
            top_k=top_k,
        )
    if agent_name == "enhanced_v2":
        return EnhancedSkillAgentV2(
            model=model,
            retriever=retriever,
            max_steps=max_steps,
            top_k=top_k,
            ablation=ablation,
        )
    if agent_name == "enhanced_v3":
        return EnhancedSkillAgentV3(
            model=model,
            retriever=retriever,
            max_steps=max_steps,
            top_k=top_k,
            ablation=ablation,
        )
    if agent_name == "enhanced_v4":
        return EnhancedSkillAgentV4(
            model=model,
            retriever=retriever,
            max_steps=max_steps,
            top_k=top_k,
            ablation=ablation,
        )
    if agent_name == "enhanced_v5":
        return EnhancedSkillAgentV5(
            model=model,
            retriever=retriever,
            max_steps=max_steps,
            top_k=top_k,
            ablation=ablation,
        )
    raise ValueError(f"Unknown agent: {agent_name}")


def error_result(task: dict, exc: Exception) -> dict:
    return {
        "task_id": task.get("task_id", ""),
        "instruction": task.get("instruction", ""),
        "gold_skills": task.get("gold_skills", []),
        "expected_answer": task.get("expected_answer", ""),
        "task_type": task.get("task_type", ""),
        "retrieved_skills": [],
        "called_skills": [],
        "observations": [],
        "final_answer": "",
        "invalid_call": True,
        "raw_model_outputs": [f"task failed: {exc}"],
        "error": str(exc),
    }


def main() -> None:
    args = parse_args()
    output_path = (
        Path(args.output)
        if args.output
        else default_output_path(args.agent, args.retriever, args.ablation)
    )
    output_path.parent.mkdir(parents=True, exist_ok=True)

    tasks = load_tasks(args)
    model = LocalLlamaModel(model_path=args.model_path)
    retriever = build_retriever(args.retriever)
    agent = build_agent(args.agent, model, retriever, args.max_steps, args.top_k, args.ablation)

    completed = 0
    with output_path.open("w", encoding="utf-8") as file:
        for index, task in enumerate(tasks, start=1):
            try:
                result = agent.run_task(task)
            except Exception as exc:
                result = error_result(task, exc)

            result["evaluation"] = evaluate_skillbench_result(result)
            result["model_path"] = str(args.model_path)
            result["model_name"] = Path(args.model_path).name
            result["ablation"] = args.ablation
            if args.agent != "enhanced_v2":
                result["ablation_config"] = {}
            if "expected_checks" in task:
                result["expected_checks"] = task["expected_checks"]
            file.write(json.dumps(result, ensure_ascii=False) + "\n")
            file.flush()
            completed += 1

            called = ",".join(result.get("called_skills", [])) or "NONE"
            invalid = result.get("invalid_call", False)
            print(
                f"[{index}/{len(tasks)}] {result.get('task_id')} "
                f"called={called} invalid={invalid} "
                f"eval={result['evaluation']}"
            )

    print(f"\nCompleted {completed} task(s).")
    print(f"Saved JSONL: {output_path}")


if __name__ == "__main__":
    main()
