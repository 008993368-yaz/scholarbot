# app.py
"""ScholarBot — Streamlit chat UI for CSUSB library search."""
from __future__ import annotations

import os
import uuid
from typing import Any

import pandas as pd
import streamlit as st
from dotenv import load_dotenv

from agents.scholar_agent import ChatReply, create_scholar_agent
from core.utils.logging_utils import get_logger

load_dotenv()

_log = get_logger(__name__)

st.set_page_config(
    page_title="ScholarBot - CSUSB Library Assistant",
    page_icon="📚",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown(
    """
<style>
    .main-header {
        font-size: 2.5rem;
        font-weight: bold;
        color: #1E40AF;
        text-align: center;
        margin-bottom: 0.5rem;
    }
    .sub-header {
        font-size: 1.2rem;
        color: #64748B;
        text-align: center;
        margin-bottom: 2rem;
    }
</style>
""",
    unsafe_allow_html=True,
)


def initialize_session_state() -> None:
    if "messages" not in st.session_state:
        st.session_state.messages = []
    if "thread_id" not in st.session_state:
        st.session_state.thread_id = str(uuid.uuid4())
    if "agent" not in st.session_state:
        with st.spinner("Initializing ScholarBot..."):
            try:
                if not os.getenv("OPENROUTER_API_KEY"):
                    st.error(
                        "OPENROUTER_API_KEY is not set. Copy `.env.example` to `.env` "
                        "and add your key from https://openrouter.ai/settings/keys"
                    )
                    st.stop()
                st.session_state.agent = create_scholar_agent()
                _log.info("Agent initialized successfully")
            except Exception as e:
                st.error(f"Failed to initialize agent: {e}")
                _log.error("Agent initialization failed: %s", e)
                st.stop()


def render_results_table(results: list[dict[str, Any]], total: int = 0) -> None:
    """Render library hits as an interactive Streamlit table."""
    if not results:
        return
    df = pd.DataFrame(results)
    # Ensure expected columns exist and order them
    for col in ("#", "Title", "Authors", "Year", "Type", "Link"):
        if col not in df.columns:
            df[col] = None
    df = df[["#", "Title", "Authors", "Year", "Type", "Link"]]
    showing = len(df)
    caption = f"Showing {showing}" + (f" of {total}" if total else "") + " results"
    st.caption(caption)
    st.dataframe(
        df,
        hide_index=True,
        use_container_width=True,
        column_config={
            "#": st.column_config.NumberColumn("#", width="small"),
            "Title": st.column_config.TextColumn("Title", width="large"),
            "Authors": st.column_config.TextColumn("Authors", width="medium"),
            "Year": st.column_config.TextColumn("Year", width="small"),
            "Type": st.column_config.TextColumn("Type", width="small"),
            "Link": st.column_config.LinkColumn("Link", display_text="Open"),
        },
    )


def render_assistant_message(message: dict[str, Any]) -> None:
    with st.chat_message("assistant", avatar="📚"):
        results = message.get("results") or []
        total = int(message.get("total") or 0)
        if results:
            render_results_table(results, total)
        content = message.get("content") or ""
        if content:
            st.markdown(content)


def display_chat_history() -> None:
    for message in st.session_state.messages:
        if message["role"] == "user":
            with st.chat_message("user"):
                st.markdown(message["content"])
        else:
            render_assistant_message(message)


def main() -> None:
    st.markdown('<div class="main-header">📚 ScholarBot</div>', unsafe_allow_html=True)
    st.markdown(
        '<div class="sub-header">Your AI-Powered CSUSB Library Research Assistant</div>',
        unsafe_allow_html=True,
    )

    initialize_session_state()

    with st.sidebar:
        st.header("About ScholarBot")
        st.markdown(
            """
**ScholarBot** helps you find academic resources from the CSUSB library using natural language.

**What I can do:**
- Search for articles, books, journals, and dissertations
- Filter by publication date
- Understand natural language queries
- Keep context across follow-up questions
- Ask clarifying questions when your request is vague

**Example queries:**
- "Find papers on machine learning"
- "Show me recent articles about climate change"
- "I need books on data science from 2020"
- "Show only books from 2023" *(after a prior search)*
"""
        )
        st.divider()
        if st.button("Clear conversation", use_container_width=True):
            st.session_state.messages = []
            st.session_state.thread_id = str(uuid.uuid4())
            st.rerun()
        st.caption(f"Thread: `{st.session_state.thread_id[:8]}…`")

    display_chat_history()

    if prompt := st.chat_input("Ask about library resources…"):
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)

        with st.chat_message("assistant", avatar="📚"):
            reply = ChatReply(text="")
            try:
                with st.status("ScholarBot is working…", expanded=True) as status:
                    for kind, payload in st.session_state.agent.chat_events(
                        prompt,
                        thread_id=st.session_state.thread_id,
                    ):
                        if kind == "status":
                            status.write(payload)
                            status.update(label=payload, state="running")
                        elif kind == "done":
                            reply = payload
                            status.update(label="Done", state="complete", expanded=False)
                        elif kind == "error":
                            reply = payload
                            status.update(label="Something went wrong", state="error", expanded=True)
            except Exception as e:
                _log.exception("Chat failed")
                reply = ChatReply(text=f"Sorry, something went wrong: {e}")

            if reply.results:
                render_results_table(reply.results, reply.total)
            if reply.text:
                st.markdown(reply.text)

        st.session_state.messages.append(
            {
                "role": "assistant",
                "content": reply.text,
                "results": reply.results,
                "total": reply.total,
            }
        )


if __name__ == "__main__":
    main()
