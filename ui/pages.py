import json
from collections import Counter
from datetime import datetime
from pathlib import Path

import pandas as pd
import streamlit as st

from config import RESULTS_DIR
from eval.evaluate import compute_metrics, load_jsonl, save_metrics_csv
from eval.skillbench_eval import evaluate_skillbench_result
from scripts.analyze_failures import classify_failure, failure_case
from ui.chat_store import append_message, create_session, load_session, save_session
from ui.common import (
    compact_skill_rows,
    dataframe_from_records,
    format_score,
    get_model,
    get_retriever,
    list_jsonl_files,
    load_benchmark,
    load_skill_library,
    method_from_label,
    model_file_status,
    read_jsonl,
    render_pipeline,
    build_agent,
)


def overview_page() -> None:
    st.title("总览")
    st.caption("本地 Llama2 的 SkillBench-Mini 实验工作台")

    tasks = load_benchmark()
    skills = load_skill_library()
    ok, model_status = model_file_status()
    run_files = list_jsonl_files()

    cols = st.columns(5)
    cols[0].metric("Benchmark 任务", len(tasks))
    cols[1].metric("Skill 数量", len(skills))
    cols[2].metric("运行日志", len(run_files))
    cols[3].metric("本地模型", "Ready" if ok else "Missing")
    cols[4].metric("运行模式", "离线")
    st.info(model_status)

    st.subheader("最小 Agent Pipeline")
    render_pipeline()

    left, right = st.columns([0.62, 0.38])
    with left:
        st.subheader("最近运行")
        rows = [
            {
                "file": path.name,
                "size_kb": f"{path.stat().st_size / 1024:.1f}",
                "updated": datetime.fromtimestamp(path.stat().st_mtime).strftime("%Y-%m-%d %H:%M"),
            }
            for path in run_files[:8]
        ]
        st.dataframe(dataframe_from_records(rows), width="stretch", hide_index=True)

    with right:
        st.subheader("最新指标")
        if run_files:
            metrics = compute_metrics(load_jsonl(run_files[0]))
            for name, value in metrics.items():
                if isinstance(value, float):
                    st.write(f"**{name}**: {value:.4f}")
                else:
                    st.write(f"**{name}**: {value}")
        else:
            st.write("暂无 JSONL 运行日志。")


def benchmark_page() -> None:
    st.title("Benchmark")
    st.caption("SkillBench-Mini 数据集检查与任务分布")

    tasks = load_benchmark()
    skills = load_skill_library()
    skill_names = {skill["name"] for skill in skills}
    task_ids = [task.get("task_id") for task in tasks]
    task_types = Counter(task.get("task_type", "") for task in tasks)
    covered = {skill for task in tasks for skill in task.get("gold_skills", [])}

    cols = st.columns(5)
    cols[0].metric("总任务", len(tasks))
    cols[1].metric("single_skill", task_types.get("single_skill", 0))
    cols[2].metric("multi_skill", task_types.get("multi_skill", 0))
    cols[3].metric("no_tool", task_types.get("no_tool", 0))
    cols[4].metric("覆盖 Skills", f"{len(covered)}/{len(skill_names)}")

    check_rows = [
        {"检查项": "字段完整", "状态": "OK" if _benchmark_fields_ok(tasks) else "FAIL"},
        {"检查项": "task_id 无重复", "状态": "OK" if len(task_ids) == len(set(task_ids)) else "FAIL"},
        {"检查项": "gold_skills 有效", "状态": "OK" if covered <= skill_names else "FAIL"},
        {"检查项": "任务数量符合要求", "状态": "OK" if len(tasks) >= 30 else "FAIL"},
    ]

    left, right = st.columns([0.64, 0.36])
    with left:
        st.subheader("任务类型分布")
        st.bar_chart(pd.DataFrame({"count": dict(task_types)}).T)
        st.subheader("Skill 覆盖")
        coverage = [{"skill": name, "covered": name in covered} for name in sorted(skill_names)]
        st.dataframe(pd.DataFrame(coverage), width="stretch", hide_index=True)
    with right:
        st.subheader("数据质量检查")
        st.dataframe(pd.DataFrame(check_rows), width="stretch", hide_index=True)

    st.subheader("任务列表")
    columns = ["task_id", "instruction", "task_type", "gold_skills", "expected_answer", "notes"]
    st.dataframe(pd.DataFrame(tasks)[columns], width="stretch", hide_index=True)


def retriever_page() -> None:
    st.title("检索器实验")
    st.caption("比较 Full Prompt、BM25 与 Embedding 的 skill retrieval 效果")

    tasks = load_benchmark()
    sample_labels = ["自定义输入"] + [
        f"{task['task_id']} | {task['instruction'][:70]}" for task in tasks[:10]
    ]
    sample = st.selectbox("选择样例任务", sample_labels)
    default_query = "" if sample == "自定义输入" else tasks[sample_labels.index(sample) - 1]["instruction"]
    query = st.text_area("Query / instruction", value=default_query or "Calculate 12 * (3 + 4)", height=90)

    control_cols = st.columns([0.34, 0.2, 0.23, 0.23])
    method_label = control_cols[0].segmented_control(
        "Retriever",
        ["Full", "BM25", "Embedding"],
        default="BM25",
    )
    top_k = control_cols[1].number_input("Top-K", min_value=1, max_value=10, value=5)
    run_clicked = control_cols[2].button("检索", width="stretch")
    batch_clicked = control_cols[3].button("测试前 10 条", width="stretch")

    method = method_from_label(method_label)
    if run_clicked:
        _render_retrieval_result(method, query, int(top_k), tasks, sample, sample_labels)

    if batch_clicked:
        rows = []
        with st.spinner("正在检索前 10 条任务..."):
            retriever = get_retriever(method)
            for task in tasks[:10]:
                retrieved = retriever.retrieve(task["instruction"], top_k=int(top_k))
                names = [skill.get("name", "") for skill in retrieved]
                gold = task.get("gold_skills", [])
                hit = bool(gold) and all(skill in names for skill in gold)
                rows.append(
                    {
                        "task_id": task["task_id"],
                        "gold_skills": ", ".join(gold),
                        "retrieved": ", ".join(names),
                        "hit": hit,
                    }
                )
        st.subheader("前 10 条检索测试")
        st.dataframe(pd.DataFrame(rows), width="stretch", hide_index=True)


def agent_run_page() -> None:
    st.title("Agent 运行")
    st.caption("运行 task -> retrieval -> skill calling -> observation -> final answer")

    method, top_k, max_steps = _agent_controls(prefix="agent_page")
    single_task = st.text_area("单条任务调试", value="Calculate 12 * (3 + 4)", height=90)
    if st.button("运行单条任务", type="primary"):
        task = _ad_hoc_task(single_task)
        with st.spinner("正在调用本地模型和 Skill Agent..."):
            agent = build_agent(method, int(top_k), int(max_steps))
            result = agent.run_task(task)
            result["evaluation"] = evaluate_skillbench_result(result)
            st.session_state["agent_single_result"] = result

    result = st.session_state.get("agent_single_result")
    if result:
        _render_agent_result(result)

    st.divider()
    st.subheader("Benchmark 批量运行")
    tasks = load_benchmark()
    batch_cols = st.columns([0.22, 0.38, 0.2, 0.2])
    max_tasks = batch_cols[0].number_input("最大任务数", min_value=1, max_value=len(tasks), value=min(5, len(tasks)))
    default_output = RESULTS_DIR / f"ui_run_{method}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.jsonl"
    output_path = batch_cols[1].text_input("输出 JSONL", value=str(default_output))
    run_batch = batch_cols[2].button("开始运行", width="stretch")
    batch_cols[3].caption("建议不要并发运行多个 Llama 任务。")

    if run_batch:
        _run_benchmark_in_ui(tasks[: int(max_tasks)], method, int(top_k), int(max_steps), Path(output_path))


def evaluation_page() -> None:
    st.title("评估指标")
    st.caption("从 results/*.jsonl 统计 Agent baseline 表现")

    files = list_jsonl_files()
    if not files:
        st.warning("results/ 下暂无 JSONL 运行日志。")
        return

    selected = st.selectbox("选择运行日志", files, format_func=lambda path: path.name)
    metrics = compute_metrics(load_jsonl(selected))

    cols = st.columns(5)
    cols[0].metric("Skill Recall@K", f"{metrics['skill_recall']:.2%}")
    cols[1].metric("选择准确率", f"{metrics['skill_selection_acc']:.2%}")
    cols[2].metric("任务成功率", f"{metrics['task_success_rate']:.2%}")
    cols[3].metric("无效调用率", f"{metrics['invalid_call_rate']:.2%}")
    cols[4].metric("平均步数", f"{metrics['avg_steps']:.2f}")

    st.subheader("指标表")
    st.dataframe(pd.DataFrame([metrics]), width="stretch", hide_index=True)

    output_path = RESULTS_DIR / f"metrics_{Path(selected).stem}.csv"
    if st.button("保存 CSV", type="primary"):
        saved = save_metrics_csv(metrics, output_path)
        st.success(f"已保存：{saved}")

    rows = read_jsonl(selected)
    type_rows = []
    for task_type, group in _group_by(rows, "task_type").items():
        type_rows.append({"task_type": task_type, **compute_metrics(group)})
    if type_rows:
        st.subheader("按任务类型拆分")
        st.dataframe(pd.DataFrame(type_rows), width="stretch", hide_index=True)


def failure_page() -> None:
    st.title("失败分析")
    st.caption("定位 retrieval、selection、execution 与 final answer 问题")

    files = list_jsonl_files()
    if not files:
        st.warning("results/ 下暂无 JSONL 运行日志。")
        return

    selected = st.selectbox("选择运行日志", files, format_func=lambda path: path.name)
    rows = read_jsonl(selected)
    cases = []
    counts = Counter()
    for row in rows:
        failure_type = classify_failure(row)
        if failure_type:
            counts[failure_type] += 1
            cases.append(failure_case(row, failure_type))

    failure_types = [
        "retrieval_failure",
        "selection_failure",
        "invalid_call",
        "execution_failure",
        "final_answer_failure",
        "unnecessary_tool_call",
    ]
    cols = st.columns(3)
    for index, failure_type in enumerate(failure_types):
        cols[index % 3].metric(failure_type, counts.get(failure_type, 0))

    filter_type = st.selectbox("失败类型过滤", ["全部"] + failure_types)
    filtered = cases if filter_type == "全部" else [case for case in cases if case["failure_type"] == filter_type]
    st.subheader("失败案例")
    st.dataframe(pd.DataFrame(filtered), width="stretch", hide_index=True)

    if filtered:
        selected_case_id = st.selectbox("查看案例详情", [case["task_id"] for case in filtered])
        selected_case = next(case for case in filtered if case["task_id"] == selected_case_id)
        st.json(selected_case)

    output_path = RESULTS_DIR / f"failure_cases_{Path(selected).stem}.json"
    if st.button("保存失败案例 JSON", type="primary"):
        payload = {
            "input": str(selected),
            "num_tasks": len(rows),
            "num_failures": len(cases),
            "failure_counts": dict(counts),
            "failure_cases": cases,
        }
        output_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        st.success(f"已保存：{output_path}")


def free_chat_page(session_id: str | None) -> None:
    st.title("自由对话")
    st.caption("聊天记录自动保存，可直接体验本地 Llama2 或 Skill Agent 调用能力")

    if not session_id:
        session = create_session()
        st.session_state["active_chat_id"] = session["id"]
    else:
        session = load_session(session_id) or create_session()
        st.session_state["active_chat_id"] = session["id"]

    top_cols = st.columns([0.28, 0.18, 0.16, 0.16, 0.22])
    mode = top_cols[0].segmented_control(
        "模式",
        ["直接问模型", "使用 Skill Agent"],
        default=session.get("mode", "使用 Skill Agent"),
    )
    retriever_label = top_cols[1].selectbox(
        "Retriever",
        ["BM25", "Full", "Embedding"],
        index=["bm25", "full", "embedding"].index(session.get("retriever", "bm25"))
        if session.get("retriever", "bm25") in ["bm25", "full", "embedding"]
        else 0,
    )
    top_k = top_cols[2].number_input("Top-K", min_value=1, max_value=10, value=5)
    max_steps = top_cols[3].number_input("Max Steps", min_value=1, max_value=4, value=2)
    top_cols[4].markdown('<span class="status-pill">当前对话已自动保存</span>', unsafe_allow_html=True)

    session["mode"] = mode
    session["retriever"] = method_from_label(retriever_label)
    save_session(session)

    chat_col, debug_col = st.columns([0.66, 0.34])
    with chat_col:
        st.subheader(session.get("title", "新对话"))
        for message in session.get("messages", []):
            with st.chat_message(message["role"]):
                st.write(message.get("content", ""))
                if message.get("debug", {}).get("called_skills"):
                    st.caption("调用 skill: " + ", ".join(message["debug"]["called_skills"]))

        with st.form("free_chat_input", clear_on_submit=True):
            prompt = st.text_input("请输入问题，例如：Calculate 12 * (3 + 4)")
            submitted = st.form_submit_button("发送", type="primary")
            show_debug = st.checkbox("显示调试信息", value=True)
            st.caption("保存对话：开启")

        if submitted and prompt.strip():
            _handle_free_chat_submit(
                session=session,
                prompt=prompt.strip(),
                mode=mode,
                retriever_name=method_from_label(retriever_label),
                top_k=int(top_k),
                max_steps=int(max_steps),
            )
            st.rerun()

    with debug_col:
        if show_debug:
            st.subheader("调试面板")
            _render_debug_panel(_latest_debug(session))


def _handle_free_chat_submit(
    session: dict,
    prompt: str,
    mode: str,
    retriever_name: str,
    top_k: int,
    max_steps: int,
) -> None:
    append_message(session, "user", prompt)
    if mode == "直接问模型":
        with st.spinner("正在调用本地 Llama2..."):
            answer = get_model().generate(f"[INST]\n{prompt}\n[/INST]", max_tokens=512, temperature=0.0)
        debug = {
            "retrieved_skills": [],
            "called_skills": [],
            "observations": [],
            "raw_model_outputs": [answer],
        }
    else:
        with st.spinner("正在运行 Skill Agent..."):
            agent = build_agent(retriever_name, top_k, max_steps)
            result = agent.run_task(_ad_hoc_task(prompt))
        answer = result.get("final_answer", "")
        debug = result
    append_message(session, "assistant", answer or "(空响应)", debug=debug)
    save_session(session)


def _latest_debug(session: dict) -> dict:
    for message in reversed(session.get("messages", [])):
        if message.get("debug"):
            return message["debug"]
    return {}


def _render_debug_panel(debug: dict) -> None:
    if not debug:
        st.info("暂无调试信息。发送一条消息后会显示 retrieved skills、called skills、observations 和 raw model output。")
        return
    st.write("**retrieved skills**")
    retrieved = debug.get("retrieved_skills", [])
    if retrieved:
        st.dataframe(pd.DataFrame(compact_skill_rows(retrieved)), width="stretch", hide_index=True)
    else:
        st.caption("无")
    st.write("**called skills**")
    st.write(", ".join(debug.get("called_skills", [])) or "无")
    st.write("**observations**")
    st.json(debug.get("observations", []))
    st.write("**raw model output**")
    st.json(debug.get("raw_model_outputs", []))


def _render_retrieval_result(
    method: str,
    query: str,
    top_k: int,
    tasks: list[dict],
    sample: str,
    sample_labels: list[str],
) -> None:
    with st.spinner("正在检索 candidate skills..."):
        retriever = get_retriever(method)
        retrieved = retriever.retrieve(query, top_k=top_k)
    st.subheader("Retrieved Skills")
    st.dataframe(pd.DataFrame(compact_skill_rows(retrieved)), width="stretch", hide_index=True)

    if sample != "自定义输入":
        task = tasks[sample_labels.index(sample) - 1]
        names = [skill.get("name", "") for skill in retrieved]
        gold = task.get("gold_skills", [])
        hit = all(skill in names for skill in gold)
        st.write(f"Gold Skills: `{', '.join(gold)}`")
        st.write("Hit" if hit else "Miss")


def _agent_controls(prefix: str) -> tuple[str, int, int]:
    cols = st.columns([0.3, 0.18, 0.18, 0.34])
    method_label = cols[0].segmented_control(
        "Retriever",
        ["Full", "BM25", "Embedding"],
        default="BM25",
        key=f"{prefix}_retriever",
    )
    top_k = cols[1].number_input("Top-K", min_value=1, max_value=10, value=5, key=f"{prefix}_topk")
    max_steps = cols[2].number_input("Max Steps", min_value=1, max_value=4, value=2, key=f"{prefix}_steps")
    cols[3].markdown('<span class="status-pill">本地模型按需加载</span>', unsafe_allow_html=True)
    return method_from_label(method_label), int(top_k), int(max_steps)


def _render_agent_result(result: dict) -> None:
    cols = st.columns(4)
    cols[0].metric("called_skills", ", ".join(result.get("called_skills", [])) or "NONE")
    cols[1].metric("invalid_call", str(bool(result.get("invalid_call", False))))
    cols[2].metric("observations", len(result.get("observations", [])))
    cols[3].metric("final_answer", "非空" if result.get("final_answer") else "空")

    st.subheader("Final Answer")
    st.write(result.get("final_answer", ""))

    st.subheader("Trace")
    st.json(
        {
            "retrieved_skills": result.get("retrieved_skills", []),
            "called_skills": result.get("called_skills", []),
            "observations": result.get("observations", []),
            "raw_model_outputs": result.get("raw_model_outputs", []),
            "evaluation": result.get("evaluation", {}),
        }
    )


def _run_benchmark_in_ui(
    tasks: list[dict],
    method: str,
    top_k: int,
    max_steps: int,
    output_path: Path,
) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    progress = st.progress(0)
    status = st.empty()
    results = []
    agent = build_agent(method, top_k, max_steps)

    with output_path.open("w", encoding="utf-8") as file:
        for index, task in enumerate(tasks, start=1):
            status.write(f"正在运行 {index}/{len(tasks)}: {task.get('task_id')}")
            try:
                result = agent.run_task(task)
            except Exception as exc:
                result = {
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
            result["evaluation"] = evaluate_skillbench_result(result)
            file.write(json.dumps(result, ensure_ascii=False) + "\n")
            file.flush()
            results.append(result)
            progress.progress(index / len(tasks))

    st.success(f"已完成 {len(results)} 条任务，保存到：{output_path}")
    st.dataframe(
        pd.DataFrame(
            [
                {
                    "task_id": item.get("task_id"),
                    "called_skills": ", ".join(item.get("called_skills", [])),
                    "invalid_call": item.get("invalid_call", False),
                    "final_answer": item.get("final_answer", "")[:120],
                }
                for item in results
            ]
        ),
        width="stretch",
        hide_index=True,
    )


def _benchmark_fields_ok(tasks: list[dict]) -> bool:
    required = {"task_id", "instruction", "gold_skills", "expected_answer", "task_type", "notes"}
    return all(required <= set(task) for task in tasks)


def _ad_hoc_task(instruction: str) -> dict:
    return {
        "task_id": "ui_ad_hoc",
        "instruction": instruction,
        "gold_skills": [],
        "expected_answer": "",
        "task_type": "ad_hoc",
        "notes": "Created from Streamlit UI.",
    }


def _group_by(rows: list[dict], field: str) -> dict[str, list[dict]]:
    groups: dict[str, list[dict]] = {}
    for row in rows:
        groups.setdefault(str(row.get(field, "")), []).append(row)
    return groups
