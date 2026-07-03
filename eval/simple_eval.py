def evaluate_trace(trace: dict) -> dict:
    retrieved_skills = trace.get("retrieved_skills", [])
    retrieved_names = {skill.get("name") for skill in retrieved_skills if isinstance(skill, dict)}
    selected_skill = trace.get("skill_name", "")
    observation = str(trace.get("observation", "")).strip()
    final_answer = str(trace.get("final_answer", "")).strip()

    checks = {
        "retrieval_success": bool(retrieved_skills),
        "selected_skill_in_retrieval": selected_skill in retrieved_names,
        "skill_called": bool(selected_skill),
        "observation_non_empty": bool(observation),
        "final_answer_non_empty": bool(final_answer),
    }
    passed = sum(1 for value in checks.values() if value)
    checks["score"] = passed / len(checks)
    return checks
