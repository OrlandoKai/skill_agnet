def evaluate_skillbench_result(result: dict) -> dict:
    gold_skills = result.get("gold_skills", [])
    task_type = result.get("task_type", "")
    retrieved_names = [
        skill.get("name")
        for skill in result.get("retrieved_skills", [])
        if isinstance(skill, dict)
    ]
    called_names = list(result.get("called_skills", []))

    if gold_skills:
        retrieval_hit = any(skill in retrieved_names for skill in gold_skills)
        retrieval_all_hit = all(skill in retrieved_names for skill in gold_skills)
        skill_call_hit = all(skill in called_names for skill in gold_skills)
    else:
        retrieval_hit = None
        retrieval_all_hit = None
        skill_call_hit = len(called_names) == 0

    no_tool_overcall = task_type == "no_tool" and len(called_names) > 0
    final_answer = str(result.get("final_answer", "")).strip()

    return {
        "retrieval_hit": retrieval_hit,
        "retrieval_all_hit": retrieval_all_hit,
        "skill_call_hit": skill_call_hit,
        "no_tool_overcall": no_tool_overcall,
        "invalid_call": bool(result.get("invalid_call", False)),
        "final_answer_non_empty": bool(final_answer),
    }
