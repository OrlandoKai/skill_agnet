import ast
import json
import re
from typing import Any

from model.llama_wrapper import LocalLlamaModel
from skills.skill_registry import call_skill, get_skill


HIGH_RISK_CONTRACTS = {
    "percentage_calculator": (
        "Input must include the base number and the percentage operation, "
        "for example 'increase 80 by 25%' or '20% discount on 50'."
    ),
    "unit_converter": (
        "Input must include source value, source unit, and target unit, "
        "for example '10 cm to m'."
    ),
    "csv_summarizer": "Input must be the raw CSV text including header and rows.",
    "regex_extractor": (
        "Input must include the exact text to search and the requested pattern type, "
        "for example email, date, or phone."
    ),
    "translator_zh_en": "Use only for Chinese to English. Input must be Chinese text.",
    "translator_en_zh": "Use only for English to Chinese. Input must be English text.",
    "calculator": "Use only for arithmetic expressions, not statistics, ratios, dates, or units.",
    "statistics_calculator": (
        "Use for mean, median, min, max, or count. Input must include all numbers."
    ),
    "title_generator": "Use to create a title from source text, not to extract keywords.",
    "keyword_extractor": "Use to extract keywords from the provided text or previous output.",
}


class EnhancedSkillAgent:
    """Skill agent with need-tool gating, planning, and grounded final answers."""

    def __init__(self, model, retriever, max_steps: int = 2, top_k: int = 5) -> None:
        self.model = model
        self.retriever = retriever
        self.max_steps = max(1, max_steps)
        self.top_k = top_k

    def run_task(self, task: dict) -> dict:
        instruction = task["instruction"]
        raw_model_outputs: list[str] = []
        called_skills: list[str] = []
        observations: list[dict] = []
        retrieved: list[dict] = []
        invalid_call = False
        plan_valid = True

        need_tool_decision = self._decide_need_tool(instruction, raw_model_outputs)

        planned_steps: list[dict] = []
        if need_tool_decision["need_tool"]:
            retrieved = self.retriever.retrieve(instruction, top_k=self.top_k)
            planned_steps, plan_valid = self._plan_skill_calls(
                instruction=instruction,
                retrieved_skills=retrieved,
                need_tool_decision=need_tool_decision,
                raw_model_outputs=raw_model_outputs,
            )

            if not plan_valid:
                invalid_call = True
            else:
                invalid_call = self._execute_plan(planned_steps, called_skills, observations)

        final_answer = self._make_final_answer(
            instruction=instruction,
            observations=observations,
            raw_model_outputs=raw_model_outputs,
            need_tool_decision=need_tool_decision,
            invalid_call=invalid_call,
        )

        return {
            "task_id": task.get("task_id", ""),
            "instruction": instruction,
            "gold_skills": task.get("gold_skills", []),
            "expected_answer": task.get("expected_answer", ""),
            "task_type": task.get("task_type", ""),
            "retrieved_skills": [self._compact_skill(skill) for skill in retrieved],
            "need_tool_decision": need_tool_decision,
            "planned_skills": [step["skill"] for step in planned_steps],
            "planned_steps": planned_steps,
            "plan_valid": plan_valid,
            "called_skills": called_skills,
            "observations": observations,
            "final_answer": final_answer,
            "invalid_call": invalid_call,
            "raw_model_outputs": raw_model_outputs,
        }

    def _decide_need_tool(self, instruction: str, raw_model_outputs: list[str]) -> dict:
        rule_decision = self._rule_based_no_tool_decision(instruction)
        if rule_decision is not None:
            return rule_decision

        prompt = self._build_need_tool_prompt(instruction)
        raw_output = self.model.generate(prompt, max_tokens=192, temperature=0.0)
        raw_model_outputs.append(raw_output)
        parsed = self._parse_json(raw_output)
        if not isinstance(parsed, dict):
            return {
                "need_tool": True,
                "task_type": "single_tool",
                "reason": "Need-tool JSON could not be parsed; conservatively using tools.",
            }

        need_tool = self._coerce_bool(parsed.get("need_tool", parsed.get("tool_needed")))
        if need_tool is None:
            need_tool = True

        task_type = str(parsed.get("task_type", "") or "").strip().lower()
        if task_type not in {"direct_answer", "single_tool", "multi_tool"}:
            task_type = "single_tool" if need_tool else "direct_answer"
        if need_tool and self._looks_multi_step(instruction):
            task_type = "multi_tool"
        elif not need_tool:
            task_type = "direct_answer"
        elif task_type == "direct_answer":
            task_type = "single_tool"

        return {
            "need_tool": bool(need_tool),
            "task_type": task_type,
            "reason": str(parsed.get("reason", "") or "").strip(),
        }

    @staticmethod
    def _looks_multi_step(instruction: str) -> bool:
        lowered = instruction.lower()
        english_multi = re.search(r"\bthen\b|\bafter that\b|\bfirst\b.+\bthen\b", lowered)
        chinese_multi = re.search(r"先.+再", instruction)
        return bool(english_multi or chinese_multi)

    def _rule_based_no_tool_decision(self, instruction: str) -> dict | None:
        normalized = re.sub(r"\s+", " ", instruction.strip().lower())
        no_tool_patterns = [
            r"^(briefly\s+)?explain\b",
            r"^why\b",
            r"^what\s+is\s+the\s+purpose\b",
            r"^what\s+does\b.*\bmean\b",
            r"^what\s+is\b.*\bin one sentence\b",
            r"^describe\s+the\s+difference\b",
            r"^in\s+one\s+sentence,\s+define\b",
            r"^list\s+two\s+components\b",
            r"^state\s+one\s+reason\b",
            r"^name\s+two\s+risks\b",
            r"^say\b",
            r"^give\s+one\s+example\b",
            r"^in\s+words,\s+what\b",
        ]
        if any(re.search(pattern, normalized) for pattern in no_tool_patterns):
            return {
                "need_tool": False,
                "task_type": "direct_answer",
                "reason": "Rule-based no-tool gate matched a conceptual or explanatory question.",
            }
        return None

    def _build_need_tool_prompt(self, instruction: str) -> str:
        return f"""[INST]
You are deciding whether an agent should use a skill/tool.
Return JSON only.

Rules:
- Choose need_tool=false for conceptual questions, explanations, definitions, opinions, or meta questions about tools.
- A task may mention words like calculate, summarize, translate, JSON, or tool without needing a tool.
- Choose need_tool=true only when the user asks to transform, compute, extract, classify, validate, format, translate, execute, or analyze specific input data.
- Use task_type direct_answer, single_tool, or multi_tool.

Examples:
Instruction: Explain why a benchmark should include no-tool questions.
{{"need_tool": false, "task_type": "direct_answer", "reason": "It asks for an explanation, not tool execution."}}

Instruction: Calculate 12 * (3 + 4).
{{"need_tool": true, "task_type": "single_tool", "reason": "It asks for arithmetic computation."}}

Instruction: Translate 你好 into English, then extract keywords.
{{"need_tool": true, "task_type": "multi_tool", "reason": "It asks for two transformations."}}

Now judge only this task:
{instruction}

Return exactly one JSON object with this schema:
{{"need_tool": true_or_false, "task_type": "direct_answer|single_tool|multi_tool", "reason": "short reason"}}
[/INST]"""

    def _plan_skill_calls(
        self,
        instruction: str,
        retrieved_skills: list[dict],
        need_tool_decision: dict,
        raw_model_outputs: list[str],
    ) -> tuple[list[dict], bool]:
        if not retrieved_skills:
            return [], False

        prompt = self._build_plan_prompt(instruction, retrieved_skills, need_tool_decision)
        raw_output = self.model.generate(prompt, max_tokens=384, temperature=0.0)
        raw_model_outputs.append(raw_output)
        parsed = self._parse_json(raw_output)
        steps = self._normalize_plan_steps(parsed)
        if not steps:
            return [], False

        candidate_names = {skill["name"] for skill in retrieved_skills}
        normalized_steps = []
        step_limit = 1 if need_tool_decision.get("task_type") == "single_tool" else self.max_steps
        for step in steps[:step_limit]:
            skill_name = str(step.get("skill", "")).strip()
            skill_input = str(step.get("input", "") or "").strip()
            if skill_name.upper() == "NONE":
                continue
            if (
                not skill_name
                or skill_name not in candidate_names
                or get_skill(skill_name) is None
            ):
                return [], False
            normalized_steps.append({"skill": skill_name, "input": skill_input})

        return normalized_steps, bool(normalized_steps)

    def _build_plan_prompt(
        self,
        instruction: str,
        retrieved_skills: list[dict],
        need_tool_decision: dict,
    ) -> str:
        candidates = "\n\n".join(self._render_skill_contract(skill) for skill in retrieved_skills)
        return f"""[INST]
You are planning skill calls for a local agent.
Choose only from candidate skill names.
Return JSON only.

Task:
{instruction}

Need-tool decision:
{json.dumps(need_tool_decision, ensure_ascii=False)}

Candidate skill contracts:
{candidates}

Planning rules:
- Output at most {self.max_steps} steps.
- For single-tool tasks, output one step.
- For multi-tool tasks, output steps in the required execution order.
- Each input must contain all information required by that skill.
- Do not pass only a partial number or vague description.
- For a later step that must consume the previous step result, use exactly "$PREVIOUS_OUTPUT" as input.
- Never choose a skill outside the candidate skill names.

Examples:
{{"steps": [{{"skill": "calculator", "input": "12 * (3 + 4)"}}]}}
{{"steps": [{{"skill": "translator_zh_en", "input": "你好"}}, {{"skill": "keyword_extractor", "input": "$PREVIOUS_OUTPUT"}}]}}

Required schema:
{{"steps": [{{"skill": "candidate skill name", "input": "complete input text"}}]}}
[/INST]"""

    def _render_skill_contract(self, skill: dict) -> str:
        name = skill.get("name", "")
        input_schema = skill.get("input_schema", {})
        examples = skill.get("examples", [])
        rendered_examples = []
        for example in examples[:2]:
            if isinstance(example, dict):
                rendered_examples.append(
                    f"input={example.get('input', '')}; output={example.get('output', '')}"
                )
        extra = HIGH_RISK_CONTRACTS.get(name, "")
        return "\n".join(
            item
            for item in [
                f"- name: {name}",
                f"  description: {skill.get('description', '')}",
                f"  input_schema: {json.dumps(input_schema, ensure_ascii=False)}",
                f"  examples: {' | '.join(rendered_examples)}",
                f"  hard_rule: {extra}" if extra else "",
            ]
            if item
        )

    def _execute_plan(
        self,
        planned_steps: list[dict],
        called_skills: list[str],
        observations: list[dict],
    ) -> bool:
        for index, step in enumerate(planned_steps, start=1):
            skill_name = step["skill"]
            skill_input = self._resolve_step_input(step.get("input", ""), observations)
            output = call_skill(skill_name, skill_input)
            called_skills.append(skill_name)
            observations.append(
                {
                    "step": index,
                    "skill": skill_name,
                    "input": skill_input,
                    "output": output,
                }
            )
            if self._is_error_output(output):
                break
        return False

    def _resolve_step_input(self, raw_input: str, observations: list[dict]) -> str:
        text = str(raw_input or "").strip()
        if not observations:
            return text

        lowered = text.lower()
        if (
            not text
            or "$previous_output" in lowered
            or "{{previous_output}}" in lowered
            or "previous observation" in lowered
            or "previous output" in lowered
            or "last result" in lowered
        ):
            return str(observations[-1].get("output", ""))
        return text.replace("$PREVIOUS_OUTPUT", str(observations[-1].get("output", "")))

    def _make_final_answer(
        self,
        instruction: str,
        observations: list[dict],
        raw_model_outputs: list[str],
        need_tool_decision: dict,
        invalid_call: bool,
    ) -> str:
        if observations and any(self._is_error_output(item.get("output", "")) for item in observations):
            errors = [
                str(item.get("output", ""))
                for item in observations
                if self._is_error_output(item.get("output", ""))
            ]
            return "Tool execution failed: " + "; ".join(errors)

        if need_tool_decision.get("need_tool") and not observations:
            return "I could not complete the requested tool call because no valid skill plan was produced."

        if not need_tool_decision.get("need_tool"):
            prompt = f"""[INST]
Answer the user directly and concisely. Do not mention tools or hidden reasoning.

User question:
{instruction}
[/INST]"""
        else:
            prompt = f"""[INST]
You are writing a final answer for a skill-calling agent.
Use only the observations below. Do not add facts that are not supported by observations.
If an observation reports an error, unsupported operation, or failure, report that failure.

Task:
{instruction}

Observations:
{json.dumps(observations, ensure_ascii=False, indent=2)}

Write a concise final answer.
[/INST]"""

        try:
            raw = self.model.generate(prompt, max_tokens=256, temperature=0.0)
            raw_model_outputs.append(raw)
            if raw.strip():
                return raw.strip()
        except Exception as exc:
            raw_model_outputs.append(f"final answer generation failed: {exc}")

        if observations:
            return "; ".join(str(item["output"]) for item in observations)
        if invalid_call:
            return "I could not complete the requested tool call."
        return instruction

    def _normalize_plan_steps(self, parsed: Any) -> list[dict]:
        if isinstance(parsed, dict):
            steps = parsed.get("steps", parsed.get("plan", []))
            if isinstance(steps, dict):
                steps = [steps]
            if not steps and "skill" in parsed:
                steps = [parsed]
        else:
            return []

        if not isinstance(steps, list):
            return []

        normalized = []
        for step in steps:
            if isinstance(step, dict):
                normalized.append(step)
        return normalized

    def _parse_json(self, raw_output: str) -> dict | None:
        parsed = LocalLlamaModel.extract_json_from_text(raw_output)
        if parsed is None:
            parsed = self._repair_json(raw_output)
        return parsed if isinstance(parsed, dict) else None

    @staticmethod
    def _repair_json(text: str) -> dict | None:
        candidates = [str(text).strip()]
        match = re.search(r"\{.*\}", str(text), flags=re.DOTALL)
        if match:
            candidates.append(match.group(0))

        for candidate in candidates:
            try:
                value = ast.literal_eval(candidate)
            except Exception:
                value = None
            if isinstance(value, dict):
                return value

            normalized = candidate.replace("'", '"')
            normalized = re.sub(r",\s*}", "}", normalized)
            normalized = re.sub(r"\btrue\b", "true", normalized, flags=re.IGNORECASE)
            normalized = re.sub(r"\bfalse\b", "false", normalized, flags=re.IGNORECASE)
            try:
                value = json.loads(normalized)
            except Exception:
                value = None
            if isinstance(value, dict):
                return value
        return None

    @staticmethod
    def _coerce_bool(value) -> bool | None:
        if isinstance(value, bool):
            return value
        if isinstance(value, str):
            lowered = value.strip().lower()
            if lowered in {"true", "yes", "1", "need_tool", "tool"}:
                return True
            if lowered in {"false", "no", "0", "none", "direct_answer"}:
                return False
        return None

    @staticmethod
    def _is_error_output(output) -> bool:
        lowered = str(output).lower()
        return (
            lowered.startswith("error:")
            or "unsupported" in lowered
            or " failed:" in lowered
            or "failed" in lowered
        )

    @staticmethod
    def _compact_skill(skill: dict) -> dict:
        compact = {
            "name": skill.get("name", ""),
            "description": skill.get("description", ""),
        }
        if "score" in skill:
            compact["score"] = skill["score"]
        return compact
