from config import DEFAULT_MAX_STEPS, DEFAULT_TOP_K
from eval.simple_eval import evaluate_trace
from model.llama_wrapper import LocalLlamaModel
from retrievers.bm25_retriever import BM25SkillRetriever
from skills.skill_registry import call_skill


class SimpleAgent:
    def __init__(
        self,
        model: LocalLlamaModel | None = None,
        retriever: BM25SkillRetriever | None = None,
        top_k: int = DEFAULT_TOP_K,
        max_steps: int = DEFAULT_MAX_STEPS,
    ) -> None:
        self.model = model or LocalLlamaModel()
        self.retriever = retriever or BM25SkillRetriever()
        self.top_k = top_k
        self.max_steps = max_steps

    def run(self, task: str) -> dict:
        retrieved_skills = self.retriever.retrieve(task, top_k=self.top_k)
        decision = self._select_skill(task, retrieved_skills)
        skill_name = decision.get("skill_name") or self._fallback_skill_name(retrieved_skills)
        skill_input = decision.get("skill_input") or task

        observation = call_skill(skill_name, skill_input)
        final_answer = self._make_final_answer(task, skill_name, skill_input, observation)

        trace = {
            "task": task,
            "retrieved_skills": retrieved_skills,
            "decision": decision,
            "skill_name": skill_name,
            "skill_input": skill_input,
            "observation": observation,
            "final_answer": final_answer,
            "max_steps": self.max_steps,
        }
        trace["evaluation"] = evaluate_trace(trace)
        return trace

    def _select_skill(self, task: str, retrieved_skills: list[dict]) -> dict:
        if not retrieved_skills:
            return {"skill_name": "", "skill_input": task, "reason": "no retrieved skills"}

        candidates = "\n".join(
            f"- {skill['name']}: {skill.get('description', '')}"
            for skill in retrieved_skills
        )
        prompt = f"""[INST]
You are a skill selection module for an agent system.
Choose exactly one skill from the candidate list and prepare its input.

Task:
{task}

Candidate skills:
{candidates}

Return only valid JSON with this schema:
{{"skill_name": "<one candidate skill name>", "skill_input": "<string input for that skill>", "reason": "<short reason>"}}
[/INST]"""

        try:
            output = self.model.generate(prompt, max_tokens=256, temperature=0.0)
            parsed = LocalLlamaModel.extract_json_from_text(output)
        except Exception as exc:
            parsed = None
            output = f"LLM selection failed: {exc}"

        if not parsed or parsed.get("skill_name") not in {skill["name"] for skill in retrieved_skills}:
            first = retrieved_skills[0]
            return {
                "skill_name": first["name"],
                "skill_input": task,
                "reason": "fallback to top retrieved skill",
                "raw_model_output": output,
            }

        parsed.setdefault("skill_input", task)
        parsed.setdefault("reason", "selected by local Llama model")
        parsed["raw_model_output"] = output
        return parsed

    def _make_final_answer(
        self,
        task: str,
        skill_name: str,
        skill_input: str,
        observation: str,
    ) -> str:
        prompt = f"""[INST]
You are an agent writing the final answer after a skill call.

Task:
{task}

Called skill:
{skill_name}

Skill input:
{skill_input}

Observation:
{observation}

Write a concise final answer for the user.
[/INST]"""

        try:
            answer = self.model.generate(prompt, max_tokens=256, temperature=0.0)
        except Exception:
            answer = ""

        if not answer:
            return f"Skill `{skill_name}` returned: {observation}"
        return answer

    @staticmethod
    def _fallback_skill_name(retrieved_skills: list[dict]) -> str:
        if not retrieved_skills:
            return ""
        return retrieved_skills[0].get("name", "")
