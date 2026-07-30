import json
import re
import base64
from collections import Counter
from datetime import datetime
from pathlib import Path

import pandas as pd
import streamlit as st

from config import N_CTX, MODEL_PATH, RESULTS_DIR, VISION_MODEL_PATH, VISION_PROJECTOR_PATH
from eval.evaluate import compute_metrics, load_jsonl, save_metrics_csv
from eval.skillbench_eval import evaluate_skillbench_result
from scripts.analyze_failures import classify_failure, failure_case
from ui.chat_store import (
    append_message,
    build_recent_history,
    create_session,
    load_session,
    save_session,
    save_chat_image,
    save_chat_image_data_url,
)
from ui.common import (
    clear_text_model_cache,
    clear_vision_model_cache,
    compact_skill_rows,
    dataframe_from_records,
    discover_model_files,
    format_score,
    get_model,
    get_retriever,
    get_vision_model,
    list_jsonl_files,
    load_benchmark,
    load_skill_library,
    method_from_label,
    model_file_status,
    model_name_from_path,
    read_jsonl,
    render_pipeline,
    vision_model_status,
    build_agent,
)
from ui.paste_image_component import paste_image_box


CHAT_MAX_TOKENS = 512
QWEN3_THINKING_MAX_TOKENS = 1536
DEFAULT_GENERATION_SETTINGS = {
    "n_ctx": int(N_CTX),
    "max_tokens": int(CHAT_MAX_TOKENS),
    "thinking_max_tokens": int(QWEN3_THINKING_MAX_TOKENS),
    "temperature": 0.2,
    "top_p": 0.85,
    "top_k": 40,
    "repeat_penalty": 1.18,
    "repeat_last_n": 160,
}


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
    discovered_models = discover_model_files()
    if discovered_models:
        st.subheader("Local GGUF Models")
        st.dataframe(
            pd.DataFrame(
                [
                    {
                        "name": item["name"],
                        "size_gb": f"{item['size_gb']:.2f}",
                        "path": item["path"],
                    }
                    for item in discovered_models
                ]
            ),
            width="stretch",
            hide_index=True,
        )

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

    method, top_k, max_steps, agent_mode, model_path = _agent_controls(prefix="agent_page")
    single_tab, batch_tab = st.tabs(["单条调试", "Benchmark 批量运行"])

    with single_tab:
        single_task = st.text_area("单条任务调试", value="Calculate 12 * (3 + 4)", height=90)
        if st.button("运行单条任务", type="primary"):
            ok, status = model_file_status(model_path)
            if not ok:
                st.error(status)
            else:
                task = _ad_hoc_task(single_task)
                with st.spinner("正在调用本地模型和 Skill Agent..."):
                    agent = build_agent(method, int(top_k), int(max_steps), agent_mode, model_path)
                    result = agent.run_task(task)
                    result["evaluation"] = evaluate_skillbench_result(result)
                    result["model_path"] = model_path
                    result["model_name"] = model_name_from_path(model_path)
                    st.session_state["agent_single_result"] = result

        result = st.session_state.get("agent_single_result")
        if result:
            _render_agent_result(result)

    with batch_tab:
        st.subheader("Benchmark 批量运行")
        st.caption("用于顺序运行 SkillBench-Mini。建议不要并发启动多个 Llama 任务。")
        tasks = load_benchmark()
        batch_cols = st.columns([0.22, 0.38, 0.2, 0.2])
        max_tasks = batch_cols[0].number_input(
            "最大任务数",
            min_value=1,
            max_value=len(tasks),
            value=min(5, len(tasks)),
        )
        default_output = RESULTS_DIR / f"ui_run_{method}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.jsonl"
        output_path = batch_cols[1].text_input("输出 JSONL", value=str(default_output))
        run_batch = batch_cols[2].button("开始运行", width="stretch")
        batch_cols[3].metric("Benchmark 总数", len(tasks))

        if run_batch:
            ok, status = model_file_status(model_path)
            if not ok:
                st.error(status)
            else:
                _run_benchmark_in_ui(
                    tasks[: int(max_tasks)],
                    method,
                    int(top_k),
                    int(max_steps),
                    Path(output_path),
                    agent_mode,
                    model_path,
                )


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
        "need_tool_false_negative",
        "invalid_plan",
        "step_retrieval_failure",
        "planner_repair_failure",
        "retrieval_failure",
        "skill_selection_failure",
        "no_tool_overcall",
        "multi_skill_under_call",
        "wrong_skill_order",
        "invalid_call",
        "execution_failure",
        "input_construction_failure",
        "final_grounding_failure",
        "final_answer_hallucination",
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
    st.caption("聊天记录自动保存，可直接体验本地模型、Qwen2.5-VL 图片问答或 Skill Agent 调用能力")

    if not session_id:
        session = create_session()
        st.session_state["active_chat_id"] = session["id"]
    else:
        session = load_session(session_id) or create_session()
        st.session_state["active_chat_id"] = session["id"]

    model_path = _model_selector("free_chat", session.get("model_path", MODEL_PATH))

    top_cols = st.columns([0.24, 0.16, 0.16, 0.14, 0.14, 0.16])
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
    agent_mode_label = top_cols[4].selectbox(
        "Agent",
        ["Baseline", "Enhanced", "Enhanced V2"],
        index=_agent_mode_index(session.get("agent_mode", "baseline")),
    )
    top_cols[5].markdown('<span class="status-pill">当前对话已自动保存</span>', unsafe_allow_html=True)

    session["mode"] = mode
    session["retriever"] = method_from_label(retriever_label)
    session["agent_mode"] = _agent_mode_from_label(agent_mode_label)
    session["model_path"] = model_path
    session["model_name"] = model_name_from_path(model_path)
    save_session(session)

    show_debug = st.checkbox("显示调试信息", value=True, key="free_chat_show_debug")
    st.caption("直接问模型：只输入文本时使用当前文本模型；发送图片时自动使用本地 Qwen2.5-VL。")

    chat_col, debug_col = st.columns([0.66, 0.34])
    with chat_col:
        st.subheader(session.get("title", "新对话"))
        for message in session.get("messages", []):
            with st.chat_message(message["role"]):
                _render_chat_message_body(message)
                _render_message_attachments(message)
                if message.get("debug", {}).get("called_skills"):
                    st.caption("调用 skill: " + ", ".join(message["debug"]["called_skills"]))

        pending_uploads = []
        thinking_mode = bool(session.get("thinking_mode", False))
        generation_settings = _normalize_generation_settings(session.get("generation_settings"))
        if _is_direct_chat_mode(mode):
            thinking_mode = st.toggle(
                "Thinking 模式",
                value=thinking_mode,
                key=f"free_chat_thinking_{session['id']}",
                help="仅对 Qwen3 文本模型生效。关闭时自动使用 /no_think，开启时自动使用 /think。",
            )
            session["thinking_mode"] = bool(thinking_mode)
            save_session(session)
            generation_settings = _render_generation_settings_panel(session)
            uploader_key = st.session_state.setdefault("free_chat_image_uploader_rev", 0)
            pending_image = st.file_uploader(
                "图片附件",
                type=["png", "jpg", "jpeg", "webp"],
                accept_multiple_files=False,
                key=f"free_chat_image_uploader_{session['id']}_{uploader_key}",
                help="可以拖拽或选择图片；部分浏览器不支持直接 Ctrl+V 粘贴图片。",
                label_visibility="collapsed",
            )
            if pending_image is not None:
                pending_uploads = [pending_image]
                st.image(pending_image, caption="待发送图片", width="stretch")
            pasted_image = paste_image_box(key=f"free_chat_paste_image_{session['id']}_{uploader_key}")
            if _is_new_pasted_image(pasted_image):
                st.session_state["free_chat_pasted_image"] = pasted_image
                st.session_state["free_chat_last_paste_id"] = pasted_image.get("id")
            if st.session_state.get("free_chat_pasted_image"):
                st.image(
                    _data_url_to_bytes(st.session_state["free_chat_pasted_image"].get("data_url", "")),
                    caption="待发送粘贴图片",
                    width="stretch",
                )
        else:
            st.caption("Skill Agent 当前只支持文本输入；图片问题请切换到“直接问模型”。")

        submission = st.chat_input(
            "请输入问题；图片可拖拽/上传，浏览器支持时也可直接粘贴",
            key=f"free_chat_input_{session['id']}",
            accept_file=True,
            file_type=["png", "jpg", "jpeg", "webp"],
            max_upload_size=30,
        )
        if submission:
            prompt, uploaded_files = _parse_chat_submission(submission)
            if not uploaded_files and pending_uploads:
                uploaded_files = pending_uploads
            if uploaded_files and not _is_direct_chat_mode(mode):
                st.warning("Skill Agent 当前只支持文本输入。请切换到“直接问模型”，或去掉图片后再发送。")
                return
            attachments = _save_chat_images(session, uploaded_files[:1])
            if not attachments and st.session_state.get("free_chat_pasted_image"):
                attachments = [
                    _save_pasted_chat_image(
                        session,
                        st.session_state["free_chat_pasted_image"],
                    )
                ]
            if uploaded_files[1:]:
                st.warning("当前版本只处理第一张图片，多余图片已忽略。")
            if not prompt and attachments:
                prompt = "请描述这张图片。"
            if not prompt and not attachments:
                return
            _handle_free_chat_submit(
                session=session,
                prompt=prompt.strip(),
                mode=mode,
                retriever_name=method_from_label(retriever_label),
                top_k=int(top_k),
                max_steps=int(max_steps),
                agent_mode=session["agent_mode"],
                model_path=model_path,
                image_attachments=attachments,
                thinking_mode=bool(thinking_mode),
                generation_settings=generation_settings,
            )
            if pending_uploads:
                st.session_state["free_chat_image_uploader_rev"] = uploader_key + 1
            if attachments:
                st.session_state.pop("free_chat_pasted_image", None)
                st.session_state["free_chat_image_uploader_rev"] = uploader_key + 1
            st.rerun()

    with debug_col:
        if show_debug:
            st.subheader("调试面板")
            _render_debug_panel(_latest_debug(session))


def _default_generation_settings() -> dict:
    return dict(DEFAULT_GENERATION_SETTINGS)


def _clamp_int(value, minimum: int, maximum: int, default: int) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        parsed = default
    return max(minimum, min(maximum, parsed))


def _clamp_float(value, minimum: float, maximum: float, default: float) -> float:
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        parsed = default
    return max(minimum, min(maximum, parsed))


def _normalize_generation_settings(settings: dict | None = None) -> dict:
    normalized = _default_generation_settings()
    if isinstance(settings, dict):
        normalized.update(settings)

    normalized["n_ctx"] = _clamp_int(
        normalized.get("n_ctx"), 1024, 8192, DEFAULT_GENERATION_SETTINGS["n_ctx"]
    )
    normalized["max_tokens"] = _clamp_int(
        normalized.get("max_tokens"), 64, 4096, DEFAULT_GENERATION_SETTINGS["max_tokens"]
    )
    normalized["thinking_max_tokens"] = _clamp_int(
        normalized.get("thinking_max_tokens"),
        256,
        4096,
        DEFAULT_GENERATION_SETTINGS["thinking_max_tokens"],
    )
    normalized["temperature"] = _clamp_float(
        normalized.get("temperature"), 0.0, 2.0, DEFAULT_GENERATION_SETTINGS["temperature"]
    )
    normalized["top_p"] = _clamp_float(
        normalized.get("top_p"), 0.1, 1.0, DEFAULT_GENERATION_SETTINGS["top_p"]
    )
    normalized["top_k"] = _clamp_int(
        normalized.get("top_k"), 1, 200, DEFAULT_GENERATION_SETTINGS["top_k"]
    )
    normalized["repeat_penalty"] = _clamp_float(
        normalized.get("repeat_penalty"),
        1.0,
        2.0,
        DEFAULT_GENERATION_SETTINGS["repeat_penalty"],
    )
    normalized["repeat_last_n"] = _clamp_int(
        normalized.get("repeat_last_n"),
        0,
        2048,
        DEFAULT_GENERATION_SETTINGS["repeat_last_n"],
    )
    return normalized


def _render_generation_settings_panel(session: dict) -> dict:
    session_id = session.get("id", "default")
    settings = _normalize_generation_settings(session.get("generation_settings"))

    with st.expander("生成参数", expanded=False):
        st.caption("仅影响自由对话的直接问模型；修改 N_CTX 会重新加载文本模型，并增加显存和加载时间。")
        if st.button("重置默认参数", key=f"gen_reset_{session_id}"):
            defaults = _default_generation_settings()
            session["generation_settings"] = defaults
            save_session(session)
            for key in defaults:
                st.session_state.pop(f"gen_{key}_{session_id}", None)
            st.rerun()

        row1 = st.columns(3)
        n_ctx = row1[0].number_input(
            "N_CTX",
            min_value=1024,
            max_value=8192,
            step=512,
            value=int(settings["n_ctx"]),
            key=f"gen_n_ctx_{session_id}",
            help="上下文窗口。调大后会重新加载模型，占用更多显存/内存。",
        )
        max_tokens = row1[1].number_input(
            "max_tokens",
            min_value=64,
            max_value=4096,
            step=64,
            value=int(settings["max_tokens"]),
            key=f"gen_max_tokens_{session_id}",
        )
        thinking_max_tokens = row1[2].number_input(
            "thinking_max_tokens",
            min_value=256,
            max_value=4096,
            step=128,
            value=int(settings["thinking_max_tokens"]),
            key=f"gen_thinking_max_tokens_{session_id}",
            help="仅 Qwen3 Thinking 模式使用。",
        )

        row2 = st.columns(5)
        temperature = row2[0].number_input(
            "temperature",
            min_value=0.0,
            max_value=2.0,
            step=0.05,
            value=float(settings["temperature"]),
            format="%.2f",
            key=f"gen_temperature_{session_id}",
        )
        top_p = row2[1].number_input(
            "top_p",
            min_value=0.1,
            max_value=1.0,
            step=0.05,
            value=float(settings["top_p"]),
            format="%.2f",
            key=f"gen_top_p_{session_id}",
        )
        top_k = row2[2].number_input(
            "top_k",
            min_value=1,
            max_value=200,
            step=1,
            value=int(settings["top_k"]),
            key=f"gen_top_k_{session_id}",
        )
        repeat_penalty = row2[3].number_input(
            "repeat_penalty",
            min_value=1.0,
            max_value=2.0,
            step=0.01,
            value=float(settings["repeat_penalty"]),
            format="%.2f",
            key=f"gen_repeat_penalty_{session_id}",
        )
        repeat_last_n = row2[4].number_input(
            "repeat_last_n",
            min_value=0,
            max_value=2048,
            step=16,
            value=int(settings["repeat_last_n"]),
            key=f"gen_repeat_last_n_{session_id}",
        )

    updated = _normalize_generation_settings(
        {
            "n_ctx": n_ctx,
            "max_tokens": max_tokens,
            "thinking_max_tokens": thinking_max_tokens,
            "temperature": temperature,
            "top_p": top_p,
            "top_k": top_k,
            "repeat_penalty": repeat_penalty,
            "repeat_last_n": repeat_last_n,
        }
    )
    session["generation_settings"] = updated
    save_session(session)
    return updated


def _handle_free_chat_submit(
    session: dict,
    prompt: str,
    mode: str,
    retriever_name: str,
    top_k: int,
    max_steps: int,
    agent_mode: str,
    model_path: str,
    image_attachments: list[dict] | None = None,
    thinking_mode: bool = False,
    generation_settings: dict | None = None,
) -> None:
    image_attachments = image_attachments or []
    image_paths = [
        item.get("model_path") or item["path"]
        for item in image_attachments
        if item.get("type") == "image" and item.get("path")
    ]
    if _is_direct_chat_mode(mode) and image_paths:
        ok, status = vision_model_status()
    else:
        ok, status = model_file_status(model_path)
    if not ok:
        st.error(status)
        return

    history_text = build_recent_history(session)
    append_message(session, "user", prompt, attachments=image_attachments)
    if _is_direct_chat_mode(mode):
        if image_paths:
            with st.spinner("正在调用本地 Qwen2.5-VL..."):
                clear_text_model_cache()
                vision_prompt = _build_vision_chat_prompt(prompt, history_text)
                raw_answer = get_vision_model().generate_with_images(
                    vision_prompt,
                    image_paths=image_paths[:1],
                    max_tokens=512,
                    temperature=0.0,
                )
                answer = _naturalize_memory_answer(raw_answer)
            debug = {
                "retrieved_skills": [],
                "called_skills": [],
                "observations": [],
                "model_path": VISION_MODEL_PATH,
                "model_name": model_name_from_path(VISION_MODEL_PATH),
                "selected_text_model_path": model_path,
                "selected_text_model_name": model_name_from_path(model_path),
                "vision_model_path": VISION_MODEL_PATH,
                "vision_projector_path": VISION_PROJECTOR_PATH,
                "image_path": image_paths[0],
                "image_paths": image_paths[:1],
                "display_image_path": image_attachments[0].get("path", "") if image_attachments else "",
                "used_vision_model": True,
                "memory_context": history_text,
                "raw_model_outputs": [raw_answer],
            }
        else:
            with st.spinner("正在调用本地文本模型..."):
                clear_vision_model_cache()
                settings = _normalize_generation_settings(generation_settings)
                model = get_model(model_path, n_ctx=settings["n_ctx"])
                chat_max_tokens = _chat_max_tokens(model_path, thinking_mode, settings)
                if _uses_qwen_chat_template(model_path):
                    raw_answer = model.generate_chat(
                        _build_direct_chat_messages(prompt, history_text, model_path, thinking_mode),
                        max_tokens=chat_max_tokens,
                        temperature=settings["temperature"],
                        top_p=settings["top_p"],
                        top_k=settings["top_k"],
                        repeat_penalty=settings["repeat_penalty"],
                        repeat_last_n=settings["repeat_last_n"],
                        stop=["[INST]", "[/INST]"],
                    )
                else:
                    model_prompt = _build_direct_chat_prompt(prompt, history_text)
                    raw_answer = model.generate(
                        model_prompt,
                        max_tokens=chat_max_tokens,
                        temperature=settings["temperature"],
                        top_p=settings["top_p"],
                        top_k=settings["top_k"],
                        repeat_penalty=settings["repeat_penalty"],
                        repeat_last_n=settings["repeat_last_n"],
                        stop=["[INST]", "[/INST]"],
                    )
                thinking_blocks, answer_text = _split_thinking_content(raw_answer)
                answer = _naturalize_memory_answer(answer_text)
            debug = {
                "retrieved_skills": [],
                "called_skills": [],
                "observations": [],
                "model_path": model_path,
                "model_name": model_name_from_path(model_path),
                "used_vision_model": False,
                "thinking_mode": bool(thinking_mode and _is_qwen3_model(model_path)),
                "generation_settings": settings,
                "n_ctx": settings["n_ctx"],
                "max_tokens": chat_max_tokens,
                "thinking": "\n\n".join(thinking_blocks),
                "memory_context": history_text,
                "raw_model_outputs": [raw_answer],
            }
    else:
        with st.spinner("正在运行 Skill Agent..."):
            clear_vision_model_cache()
            agent = build_agent(retriever_name, top_k, max_steps, agent_mode, model_path)
            agent_instruction = _build_agent_chat_instruction(prompt, history_text)
            result = agent.run_task(_ad_hoc_task(agent_instruction))
        answer = _naturalize_memory_answer(result.get("final_answer", ""))
        result["final_answer"] = answer
        result["model_path"] = model_path
        result["model_name"] = model_name_from_path(model_path)
        debug = result
        debug["memory_context"] = history_text
    append_message(session, "assistant", answer or "(空响应)", debug=debug)
    save_session(session)


def _build_direct_chat_prompt(prompt: str, history_text: str) -> str:
    history_block = _format_earlier_turns(history_text)
    return f"""[INST]
You are a helpful assistant.
Answer naturally and directly.
Use earlier turns only to resolve pronouns or follow-up questions.
Do not explain where the answer came from.
If earlier turns are not needed, ignore them silently.

{history_block}

Current user question:
{prompt}
[/INST]"""


def _build_direct_chat_messages(
    prompt: str,
    history_text: str,
    model_path: str | Path = "",
    thinking_mode: bool = False,
) -> list[dict]:
    user_prompt = _apply_qwen3_thinking_directive(prompt, model_path, thinking_mode)
    history_block = _format_earlier_turns(history_text)
    user_content = f"{history_block}\n\nCurrent user question:\n{user_prompt}".strip()
    return [
        {
            "role": "system",
            "content": (
                "You are a helpful assistant. Answer naturally and directly. "
                "Use earlier turns only when they are relevant to the current question. "
                "If the user asks what you can see or remember, describe only the visible chat content."
            ),
        },
        {"role": "user", "content": user_content},
    ]


def _build_agent_chat_instruction(prompt: str, history_text: str) -> str:
    history_block = _format_earlier_turns(history_text)
    return f"""{history_block}

Current user request:
{prompt}

Use earlier turns only if they help resolve references like "刚才", "上一个结果", "继续", "它", or "that result".
Do not explain where the final answer came from."""


def _build_vision_chat_prompt(prompt: str, history_text: str) -> str:
    history_block = _format_earlier_turns(history_text)
    return f"""Answer the user's question about the attached image.
Answer naturally and directly.
Use earlier turns only to resolve follow-up references.
If the user asks what you can see or remember, describe only the visible chat content.

{history_block}

Current user question:
{prompt}"""


def _naturalize_memory_answer(answer: str) -> str:
    cleaned = str(answer).strip()
    if not cleaned:
        return cleaned
    cleaned = _strip_chat_template_tokens(cleaned)
    cleaned = _strip_think_blocks(cleaned)

    leading_patterns = [
        r"^[^\w\u4e00-\u9fff]+(?=(?:based on|from the|根据|it seems|it looks|i understand|well|so))",
        r"^(?:ah[,! ]*great!?|great!?|sure!?|okay!?|ok[,!]?|好的[，,！!]?)\s*(?:😊|🤖|🙂|😀)?\s*",
        r"^(?:based on (?:your|the|our) conversation history|from the conversation history|based on (?:the )?(?:private )?(?:reference )?context|based on memory)[,，]?\s*",
        r"^(?:根据(?:对话历史|我们的对话|上下文|记忆)[，,]?)\s*",
        r"^(?:it seems like|it looks like|i understand that)\s+you(?:'re| are)?\s+(?:asking|wondering)[^.?!。！？]*[.?!。！？]\s*",
        r"^(?:看起来|我理解)?你(?:是)?(?:在)?问(?:的是)?[^。！？]*[。！？]\s*",
        r"^(?:well|so)[,，]\s*",
    ]

    changed = True
    while changed:
        changed = False
        for pattern in leading_patterns:
            new_cleaned = re.sub(pattern, "", cleaned, flags=re.IGNORECASE).lstrip()
            if new_cleaned != cleaned:
                cleaned = new_cleaned
                changed = True

    trailing_patterns = [
        r"\s+You introduced yourself earlier in (?:the|our) conversation\.",
        r"\s+You mentioned (?:earlier|before) that [^.?!。！？]+[.?!。！？]",
        r"\s+Is there anything else you'd like(?: to chat about| to ask)?[^\n]*$",
        r"\s+I'm here to help(?: with any questions you may have)?[^\n]*$",
        r"\s+Feel free to ask(?: me)? anything[^\n]*$",
    ]
    for pattern in trailing_patterns:
        cleaned = re.sub(pattern, "", cleaned, flags=re.IGNORECASE).strip()

    if cleaned:
        cleaned = cleaned[0].upper() + cleaned[1:] if cleaned[:1].isascii() else cleaned
    return cleaned


def _uses_qwen_chat_template(model_path: str | Path) -> bool:
    return "qwen" in Path(str(model_path)).name.lower()


def _is_qwen3_model(model_path: str | Path) -> bool:
    name = Path(str(model_path)).name.lower()
    return "qwen3" in name


def _chat_max_tokens(
    model_path: str | Path,
    thinking_mode: bool = False,
    settings: dict | None = None,
) -> int:
    settings = _normalize_generation_settings(settings)
    if thinking_mode and _is_qwen3_model(model_path):
        return settings["thinking_max_tokens"]
    return settings["max_tokens"]


def _apply_qwen3_thinking_directive(
    prompt: str,
    model_path: str | Path,
    thinking_mode: bool = False,
) -> str:
    text = str(prompt).strip()
    if not _is_qwen3_model(model_path):
        return text
    text = re.sub(r"(?im)^\s*/(?:no_)?think\s*$", "", text).strip()
    directive = "/think" if thinking_mode else "/no_think"
    return f"{text}\n\n{directive}"


def _format_earlier_turns(history_text: str) -> str:
    history = str(history_text or "").strip()
    if not history or history.lower() == "none":
        return "Earlier turns: none"
    return f"Earlier turns:\n{history}"


def _strip_chat_template_tokens(text: str) -> str:
    cleaned = re.sub(r"(?:\[/INST\]|\[INST\])", " ", str(text), flags=re.IGNORECASE)
    cleaned = re.sub(r"(?:\s*\[/\s*INST\s*\]\s*)+", " ", cleaned, flags=re.IGNORECASE)
    return re.sub(r"[ \t]{2,}", " ", cleaned).strip()


def _strip_think_blocks(text: str) -> str:
    return _split_thinking_content(text)[1]


def _split_thinking_content(text: str) -> tuple[list[str], str]:
    source = str(text or "")
    thinking_blocks = [
        match.group(1).strip()
        for match in re.finditer(r"<think>(.*?)</think>", source, flags=re.IGNORECASE | re.DOTALL)
        if match.group(1).strip()
    ]
    answer = re.sub(r"<think>.*?</think>", "", source, flags=re.IGNORECASE | re.DOTALL)

    if not thinking_blocks and re.search(r"<think>", answer, flags=re.IGNORECASE):
        before, after = re.split(r"<think>", answer, maxsplit=1, flags=re.IGNORECASE)
        if after.strip():
            thinking_blocks.append(re.sub(r"</think>", "", after, flags=re.IGNORECASE).strip())
        answer = before

    answer = re.sub(r"</?think>", "", answer, flags=re.IGNORECASE)
    answer = _strip_chat_template_tokens(answer)
    return thinking_blocks, answer.strip()


def _render_chat_message_body(message: dict) -> None:
    content = str(message.get("content", ""))
    if message.get("role") != "assistant":
        st.write(content)
        return

    debug = message.get("debug", {}) or {}
    thinking = str(debug.get("thinking", "") or "").strip()
    thinking_blocks, answer = _split_thinking_content(content)
    if not thinking and thinking_blocks:
        thinking = "\n\n".join(thinking_blocks)

    if thinking:
        with st.expander("思考过程", expanded=False):
            st.write(thinking)
    st.write(answer or "(空响应)")


def _display_chat_content(message: dict) -> str:
    content = str(message.get("content", ""))
    if message.get("role") == "assistant":
        return _strip_think_blocks(_strip_chat_template_tokens(content))
    return content


def _latest_debug(session: dict) -> dict:
    for message in reversed(session.get("messages", [])):
        if message.get("debug"):
            return message["debug"]
    return {}


def _render_message_attachments(message: dict) -> None:
    for attachment in message.get("attachments", []):
        if attachment.get("type") != "image":
            continue
        path = Path(str(attachment.get("path", "")))
        if path.exists():
            st.image(str(path), caption=attachment.get("name", path.name), width="stretch")
        else:
            st.caption(f"图片文件不存在：{path}")


def _render_debug_panel(debug: dict) -> None:
    if not debug:
        st.info("暂无调试信息。发送一条消息后会显示 retrieved skills、called skills、observations 和 raw model output。")
        return
    if "used_vision_model" in debug:
        st.write("**used vision model**")
        st.write(str(debug.get("used_vision_model")))
    if debug.get("model_name") or debug.get("model_path"):
        st.write("**model**")
        st.caption(f"{debug.get('model_name', '')} | {debug.get('model_path', '')}")
    if debug.get("vision_model_path"):
        st.write("**vision model**")
        st.caption(str(debug.get("vision_model_path")))
        st.caption(str(debug.get("vision_projector_path", "")))
    if debug.get("image_path"):
        st.write("**image**")
        st.caption(str(debug.get("image_path")))
    st.write("**retrieved skills**")
    retrieved = debug.get("retrieved_skills", [])
    if retrieved:
        st.dataframe(pd.DataFrame(compact_skill_rows(retrieved)), width="stretch", hide_index=True)
    else:
        st.caption("无")
    if "subtasks" in debug:
        st.write("**subtasks**")
        st.json(debug.get("subtasks", []))
    if "retrieved_by_step" in debug:
        st.write("**retrieved by step**")
        st.json(debug.get("retrieved_by_step", []))
    st.write("**called skills**")
    st.write(", ".join(debug.get("called_skills", [])) or "无")
    if "need_tool_decision" in debug:
        st.write("**need tool decision**")
        st.json(debug.get("need_tool_decision", {}))
    if "planned_steps" in debug:
        st.write("**planned steps**")
        st.json(debug.get("planned_steps", []))
    if "plan_valid" in debug:
        st.write("**plan valid**")
        st.write(str(debug.get("plan_valid")))
    if "plan_repaired" in debug:
        st.write("**plan repaired**")
        st.write(str(debug.get("plan_repaired")))
    if "final_answer_source" in debug:
        st.write("**final answer source**")
        st.write(str(debug.get("final_answer_source")))
    if debug.get("thinking"):
        st.write("**thinking**")
        with st.expander("思考过程", expanded=False):
            st.write(str(debug.get("thinking", "")))
    st.write("**observations**")
    st.json(debug.get("observations", []))
    st.write("**memory context**")
    st.text(debug.get("memory_context", "None"))
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


def _parse_chat_submission(submission) -> tuple[str, list]:
    if isinstance(submission, str):
        return submission.strip(), []

    text = getattr(submission, "text", None)
    files = getattr(submission, "files", None)
    if isinstance(submission, dict):
        text = submission.get("text", text)
        files = submission.get("files", files)

    if files is None:
        files = []
    elif not isinstance(files, list):
        files = [files]
    return str(text or "").strip(), list(files)


def _is_new_pasted_image(pasted_image) -> bool:
    if not isinstance(pasted_image, dict):
        return False
    paste_id = pasted_image.get("id")
    data_url = pasted_image.get("data_url", "")
    return bool(paste_id and data_url and paste_id != st.session_state.get("free_chat_last_paste_id"))


def _data_url_to_bytes(data_url: str) -> bytes:
    if "," not in data_url:
        return b""
    return base64.b64decode(data_url.split(",", 1)[1])


def _is_direct_chat_mode(mode: str) -> bool:
    return "直接" in str(mode) and "模型" in str(mode)


def _save_chat_images(session: dict, uploaded_files: list) -> list[dict]:
    attachments = []
    for uploaded_file in uploaded_files:
        attachments.append(save_chat_image(session["id"], uploaded_file))
    return attachments


def _save_pasted_chat_image(session: dict, pasted_image: dict) -> dict:
    return save_chat_image_data_url(
        session["id"],
        str(pasted_image.get("data_url", "")),
        str(pasted_image.get("name", "clipboard.png") or "clipboard.png"),
    )


def _model_selector(prefix: str, default_path: str | None = None) -> str:
    models = discover_model_files()
    model_paths = [item["path"] for item in models]
    labels = {item["path"]: item["label"] for item in models}

    default_model_path = str(default_path or st.session_state.get(f"{prefix}_model_path", MODEL_PATH))
    if default_model_path not in model_paths and Path(default_model_path).exists():
        size_gb = Path(default_model_path).stat().st_size / (1024**3)
        model_paths.insert(0, default_model_path)
        labels[default_model_path] = f"{Path(default_model_path).name} ({size_gb:.2f} GB)"

    custom_option = "__custom_model_path__"
    options = [*model_paths, custom_option]
    index = model_paths.index(default_model_path) if default_model_path in model_paths else len(options) - 1

    selected = st.selectbox(
        "Model",
        options,
        index=index,
        format_func=lambda value: "Custom GGUF path" if value == custom_option else labels.get(value, value),
        key=f"{prefix}_model_select",
    )
    if selected == custom_option:
        model_path = st.text_input(
            "Custom model path",
            value=default_model_path if default_model_path not in model_paths else "",
            key=f"{prefix}_custom_model_path",
        ).strip()
    else:
        model_path = selected

    st.session_state[f"{prefix}_model_path"] = model_path
    ok, status = model_file_status(model_path)
    if ok:
        st.caption(status)
    else:
        st.error(status)
    return model_path


def _agent_controls(prefix: str) -> tuple[str, int, int, str, str]:
    model_path = _model_selector(prefix)
    cols = st.columns([0.26, 0.16, 0.16, 0.18, 0.24])
    method_label = cols[0].segmented_control(
        "Retriever",
        ["Full", "BM25", "Embedding"],
        default="BM25",
        key=f"{prefix}_retriever",
    )
    top_k = cols[1].number_input("Top-K", min_value=1, max_value=10, value=5, key=f"{prefix}_topk")
    max_steps = cols[2].number_input("Max Steps", min_value=1, max_value=4, value=2, key=f"{prefix}_steps")
    agent_mode_label = cols[3].selectbox(
        "Agent",
        ["Baseline", "Enhanced", "Enhanced V2"],
        index=0,
        key=f"{prefix}_agent_mode",
    )
    cols[4].markdown('<span class="status-pill">本地模型按需加载</span>', unsafe_allow_html=True)
    agent_mode = _agent_mode_from_label(agent_mode_label)
    return method_from_label(method_label), int(top_k), int(max_steps), agent_mode, model_path


def _agent_mode_from_label(label: str) -> str:
    return {
        "Baseline": "baseline",
        "Enhanced": "enhanced",
        "Enhanced V2": "enhanced_v2",
    }.get(label, "baseline")


def _agent_mode_index(agent_mode: str) -> int:
    return {
        "baseline": 0,
        "enhanced": 1,
        "enhanced_v2": 2,
    }.get(agent_mode, 0)


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
            "model_name": result.get("model_name", ""),
            "model_path": result.get("model_path", ""),
            "retrieved_skills": result.get("retrieved_skills", []),
            "subtasks": result.get("subtasks", []),
            "retrieved_by_step": result.get("retrieved_by_step", []),
            "need_tool_decision": result.get("need_tool_decision", {}),
            "planned_steps": result.get("planned_steps", []),
            "plan_valid": result.get("plan_valid", None),
            "plan_repaired": result.get("plan_repaired", None),
            "called_skills": result.get("called_skills", []),
            "observations": result.get("observations", []),
            "final_answer_source": result.get("final_answer_source", ""),
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
    agent_mode: str,
    model_path: str,
) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    progress = st.progress(0)
    status = st.empty()
    results = []
    agent = build_agent(method, top_k, max_steps, agent_mode, model_path)

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
            result["model_path"] = model_path
            result["model_name"] = model_name_from_path(model_path)
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
