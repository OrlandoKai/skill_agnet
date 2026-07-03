import ast
import json
import re

from model.llama_wrapper import LocalLlamaModel
from skills.skill_registry import call_skill, get_skill


class MinimalSkillAgent:
    def __init__(self, model, retriever, max_steps: int = 2, top_k: int = 5) -> None:
        self.model = model
        self.retriever = retriever
        self.max_steps = max_steps
        self.top_k = top_k

    def run_task(self, task: dict) -> dict:
        instruction = task["instruction"]
        retrieved = self.retriever.retrieve(instruction, top_k=self.top_k)
        candidate_names = {skill["name"] for skill in retrieved}
        called_skills: list[str] = []
        observations: list[dict] = []
        raw_model_outputs: list[str] = []
        invalid_call = False

        for step in range(self.max_steps):
            prompt = self._build_action_prompt(
                instruction=instruction,
                retrieved_skills=retrieved,
                observations=observations,
                step=step + 1,
            )
            raw_output = self.model.generate(prompt, max_tokens=256, temperature=0.0)
            raw_model_outputs.append(raw_output)
            action = self._parse_action(raw_output)

            if action is None:
                invalid_call = True
                break

            skill_name = action["skill"]
            skill_input = action["input"]
            if skill_name == "NONE":
                break

            if skill_name in called_skills:
                break

            if skill_name not in candidate_names or get_skill(skill_name) is None:
                invalid_call = True
                break

            observation = call_skill(skill_name, skill_input)
            called_skills.append(skill_name)
            observations.append(
                {
                    "step": step + 1,
                    "skill": skill_name,
                    "input": skill_input,
                    "output": observation,
                }
            )
            if task.get("task_type") != "multi_skill":
                break

        final_answer = self._make_final_answer(instruction, observations, raw_model_outputs)

        return {
            "task_id": task.get("task_id", ""),
            "instruction": instruction,
            "gold_skills": task.get("gold_skills", []),
            "expected_answer": task.get("expected_answer", ""),
            "task_type": task.get("task_type", ""),
            "retrieved_skills": [self._compact_skill(skill) for skill in retrieved],
            "called_skills": called_skills,
            "observations": observations,
            "final_answer": final_answer,
            "invalid_call": invalid_call,
            "raw_model_outputs": raw_model_outputs,
        }

    def _build_action_prompt(
        self,
        instruction: str,
        retrieved_skills: list[dict],
        observations: list[dict],
        step: int,
    ) -> str:
        candidates = "\n".join(
            f"- {skill['name']}: {skill.get('description', '')}"
            for skill in retrieved_skills
        )
        previous = json.dumps(observations, ensure_ascii=False, indent=2)
        return f"""[INST]
You are a minimal skill-calling agent.
You may call at most one skill in this step.
Choose only from the candidate skill names below, or choose NONE.
If no tool is needed, or enough observations are available, choose NONE.

Instruction:
{instruction}

Candidate skills:
{candidates}

Previous observations:
{previous}

Return JSON only. Do not include markdown or explanations.
Required schema:
{{"skill": "one candidate skill name or NONE", "input": "input text"}}

Step: {step}
[/INST]"""

    def _make_final_answer(
        self,
        instruction: str,
        observations: list[dict],
        raw_model_outputs: list[str],
    ) -> str:
        prompt = f"""[INST]
You are writing the final answer for a user.
Use the task and observations. If there are no observations, answer directly.

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
        return instruction

    def _parse_action(self, raw_output: str) -> dict | None:
        parsed = LocalLlamaModel.extract_json_from_text(raw_output)
        if parsed is None:
            parsed = self._repair_json(raw_output)
        if not isinstance(parsed, dict):
            return None

        skill = parsed.get("skill", parsed.get("skill_name", ""))
        skill_input = parsed.get("input", parsed.get("skill_input", ""))
        if skill is None:
            return None

        skill = str(skill).strip()
        if not skill:
            return None
        if skill.upper() == "NONE":
            skill = "NONE"
        return {"skill": skill, "input": str(skill_input or "")}

    @staticmethod
    def _repair_json(text: str) -> dict | None:
        candidates = [text.strip()]
        match = re.search(r"\{.*\}", text, flags=re.DOTALL)
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
            try:
                value = json.loads(normalized)
            except Exception:
                value = None
            if isinstance(value, dict):
                return value
        return None

    @staticmethod
    def _compact_skill(skill: dict) -> dict:
        compact = {
            "name": skill.get("name", ""),
            "description": skill.get("description", ""),
        }
        if "score" in skill:
            compact["score"] = skill["score"]
        return compact
