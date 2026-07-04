import streamlit as st

from ui.chat_store import create_session, list_sessions
from ui.common import apply_page_style
from ui.pages import (
    agent_run_page,
    benchmark_page,
    evaluation_page,
    failure_page,
    free_chat_page,
    overview_page,
    retriever_page,
)


NAV_ITEMS = [
    {"label": "总览", "icon": "⌂"},
    {"label": "Benchmark", "icon": "▥"},
    {"label": "检索器实验", "icon": "⌕"},
    {"label": "Agent 运行", "icon": "◉"},
    {"label": "评估指标", "icon": "⌁"},
    {"label": "失败分析", "icon": "△"},
    {"label": "自由问答", "icon": "✎"},
]


def main() -> None:
    st.set_page_config(
        page_title="Skill Agent Baseline",
        page_icon="SA",
        layout="wide",
        initial_sidebar_state="expanded",
    )
    apply_page_style()

    if "page" not in st.session_state:
        st.session_state["page"] = "总览"

    with st.sidebar:
        st.title("Skill Agent")
        st.caption("Local Llama2 Workbench")
        page = render_main_sidebar()
        active_chat_id = None
        if page == "自由问答":
            active_chat_id = render_chat_sidebar()

    if page == "总览":
        overview_page()
    elif page == "Benchmark":
        benchmark_page()
    elif page == "检索器实验":
        retriever_page()
    elif page == "Agent 运行":
        agent_run_page()
    elif page == "评估指标":
        evaluation_page()
    elif page == "失败分析":
        failure_page()
    elif page == "自由问答":
        free_chat_page(active_chat_id)


def render_main_sidebar() -> str:
    labels = [item["label"] for item in NAV_ITEMS]
    if st.session_state.get("page") not in labels:
        st.session_state["page"] = "总览"

    st.markdown("#### 导航")
    for item in NAV_ITEMS:
        label = item["label"]
        active = st.session_state["page"] == label
        if st.button(
            f"{item['icon']}  {label}",
            key=f"nav_{label}",
            type="primary" if active else "secondary",
            width="stretch",
        ):
            st.session_state["page"] = label
            st.rerun()
    return st.session_state["page"]


def render_chat_sidebar() -> str | None:
    st.divider()
    st.markdown("#### 自由问答")
    if st.button("＋  新对话", type="primary", width="stretch"):
        session = create_session()
        st.session_state["active_chat_id"] = session["id"]
        st.rerun()

    query = st.text_input("搜索聊天记录", placeholder="搜索聊天记录", label_visibility="collapsed")
    st.caption("自动保存的对话")
    sessions = list_sessions()
    if query:
        sessions = [
            session
            for session in sessions
            if query.lower() in session.get("title", "").lower()
        ]

    if not sessions:
        session = create_session()
        st.session_state["active_chat_id"] = session["id"]
        sessions = [session]

    active_chat_id = st.session_state.get("active_chat_id") or sessions[0]["id"]
    for session in sessions:
        label = session.get("title", "新对话")
        mode = "Agent" if session.get("mode") == "使用 Skill Agent" else "模型"
        button_type = "primary" if session["id"] == active_chat_id else "secondary"
        if st.button(
            f"{label}\n{session.get('updated_at', '')[:16]} · {mode}",
            key=f"chat_{session['id']}",
            width="stretch",
            type=button_type,
        ):
            st.session_state["active_chat_id"] = session["id"]
            active_chat_id = session["id"]
            st.rerun()
    return active_chat_id


if __name__ == "__main__":
    main()
