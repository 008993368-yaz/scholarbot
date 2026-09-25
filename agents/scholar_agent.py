# agents/scholar_agent.py
"""LangGraph ScholarBot agent with Jev routing and OpenRouter chat."""
from __future__ import annotations

import os
import operator
from dataclasses import dataclass, field
from typing import Annotated, Any, Literal, Optional, Sequence, TypedDict

from langchain_core.messages import (
    AIMessage,
    BaseMessage,
    HumanMessage,
    SystemMessage,
    ToolMessage,
)
from langchain_openai import ChatOpenAI
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, StateGraph

from agents.prompts import (
    CHITCHAT_SYSTEM_PROMPT,
    CLARIFY_SYSTEM_PROMPT,
    EXTRACT_SYSTEM_PROMPT,
    PRESENT_SYSTEM_PROMPT,
)
from core.clients.jev_client import JevClient
from core.tools.library_tools import LIBRARY_TOOLS, run_library_search
from core.utils.logging_utils import get_logger

_log = get_logger(__name__)

OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"
# Free Llama 3.3 was removed from OpenRouter; use a free model that supports tools.
DEFAULT_CHAT_MODEL = "nex-agi/nex-n2.5-pro:free"
# Tried in order when the primary model is down / rate-limited (OpenRouter: max 3).
DEFAULT_FALLBACK_MODELS = [
    "nvidia/nemotron-3-super-120b-a12b:free",
    "qwen/qwen3.8-27b:free",
    "openrouter/free",
]


@dataclass
class ChatReply:
    """Assistant response returned to the Streamlit UI."""

    text: str
    results: list[dict[str, Any]] = field(default_factory=list)
    total: int = 0


class AgentState(TypedDict):
    """LangGraph state for ScholarBot."""

    messages: Annotated[Sequence[BaseMessage], operator.add]
    route: str
    last_topic: str
    search_results: list
    search_total: int


def _user_facing_error(exc: Exception) -> str:
    text = str(exc)
    msg = text.lower()
    if "429" in text or "rate-limited" in msg or "rate limit" in msg or "quota" in msg:
        return (
            "OpenRouter rate or usage limit reached. Wait a moment and try again, "
            "or check https://openrouter.ai/settings/keys"
        )
    if "401" in text or "403" in text or "invalid_api_key" in msg or "authentication" in msg:
        return (
            "Invalid or missing OPENROUTER_API_KEY. Set it in your .env file: "
            "https://openrouter.ai/settings/keys"
        )
    if "404" in text or "model is unavailable" in msg or "model_not_found" in msg:
        return (
            "The selected OpenRouter model is unavailable. "
            f"Set OPENROUTER_MODEL in .env (e.g. {DEFAULT_CHAT_MODEL})."
        )
    if "tool use" in msg or "tool_use" in msg:
        return (
            "That OpenRouter model does not support tool calling. "
            f"Set OPENROUTER_MODEL to a tool-capable free model (e.g. {DEFAULT_CHAT_MODEL})."
        )
    return f"Something went wrong: {exc}. Please try again or rephrase your question."


def _fallback_models(primary: str) -> list[str]:
    """Build OpenRouter fallback list (max 3), excluding the primary model."""
    raw = os.getenv("OPENROUTER_FALLBACK_MODELS", "")
    if raw.strip():
        candidates = [m.strip() for m in raw.split(",") if m.strip()]
    else:
        candidates = list(DEFAULT_FALLBACK_MODELS)
    return [m for m in candidates if m != primary][:3]


def _latest_human_text(messages: Sequence[BaseMessage]) -> str:
    for m in reversed(messages):
        if isinstance(m, HumanMessage):
            return m.content if isinstance(m.content, str) else str(m.content)
    return ""


def _recent_turn_summaries(messages: Sequence[BaseMessage], limit: int = 6) -> list[str]:
    turns: list[str] = []
    for m in messages:
        if isinstance(m, HumanMessage):
            text = m.content if isinstance(m.content, str) else str(m.content)
            turns.append(f"user: {text[:300]}")
        elif isinstance(m, AIMessage) and m.content and not getattr(m, "tool_calls", None):
            text = m.content if isinstance(m.content, str) else str(m.content)
            turns.append(f"assistant: {text[:300]}")
    return turns[-limit:]


def _infer_topic_from_tool_calls(messages: Sequence[BaseMessage]) -> Optional[str]:
    for m in reversed(messages):
        if isinstance(m, AIMessage) and getattr(m, "tool_calls", None):
            for tc in m.tool_calls:
                args = tc.get("args") if isinstance(tc, dict) else getattr(tc, "args", {})
                if isinstance(args, dict) and args.get("query"):
                    return str(args["query"])
    return None


def _tool_call_id(tc: Any) -> str:
    if isinstance(tc, dict):
        return str(tc.get("id") or "")
    return str(getattr(tc, "id", "") or "")


def _tool_call_args(tc: Any) -> dict:
    if isinstance(tc, dict):
        args = tc.get("args") or {}
    else:
        args = getattr(tc, "args", None) or {}
    return args if isinstance(args, dict) else {}


class ScholarAgent:
    """Conversational library search agent (Jev route + OpenRouter LLM + Primo tool)."""

    def __init__(
        self,
        model_name: Optional[str] = None,
        temperature: float = 0.3,
        api_key: Optional[str] = None,
    ):
        api_key = api_key or os.getenv("OPENROUTER_API_KEY", "")
        if not api_key:
            raise ValueError(
                "OPENROUTER_API_KEY is required. "
                "Set it in your .env file (https://openrouter.ai/settings/keys)."
            )

        model_name = model_name or os.getenv("OPENROUTER_MODEL", DEFAULT_CHAT_MODEL)
        fallbacks = _fallback_models(model_name)
        _log.info(
            "Initializing ScholarAgent with OpenRouter model=%s fallbacks=%s",
            model_name,
            fallbacks,
        )

        self.jev = JevClient(api_key=api_key)
        llm_kwargs: dict = {
            "base_url": OPENROUTER_BASE_URL,
            "api_key": api_key,
            "model": model_name,
            "temperature": temperature,
            "default_headers": {
                "HTTP-Referer": "https://github.com/scholarbot",
                "X-Title": "ScholarBot",
            },
        }
        if fallbacks:
            # OpenRouter tries these slugs if the primary model fails
            llm_kwargs["extra_body"] = {"models": fallbacks}
        base_llm = ChatOpenAI(**llm_kwargs)
        self.llm = base_llm
        self.llm_with_tools = base_llm.bind_tools(LIBRARY_TOOLS)
        self.memory = MemorySaver()
        self.graph = self._create_graph()
        self.app = self.graph.compile(checkpointer=self.memory)
        _log.info("ScholarAgent initialized successfully")

    def _create_graph(self) -> StateGraph:
        workflow = StateGraph(AgentState)

        workflow.add_node("route", self._route_node)
        workflow.add_node("clarify", self._clarify_node)
        workflow.add_node("extract", self._extract_node)
        workflow.add_node("tools", self._tools_node)
        workflow.add_node("present", self._present_node)
        workflow.add_node("chitchat", self._chitchat_node)

        workflow.set_entry_point("route")
        workflow.add_conditional_edges(
            "route",
            self._after_route,
            {
                "clarify": "clarify",
                "search": "extract",
                "chitchat": "chitchat",
            },
        )
        workflow.add_edge("clarify", END)
        workflow.add_edge("chitchat", END)
        workflow.add_conditional_edges(
            "extract",
            self._after_extract,
            {
                "tools": "tools",
                "end": END,
            },
        )
        workflow.add_edge("tools", "present")
        workflow.add_edge("present", END)

        return workflow

    def _route_node(self, state: AgentState) -> dict:
        messages = list(state["messages"])
        user_message = _latest_human_text(messages)
        last_topic = state.get("last_topic") or _infer_topic_from_tool_calls(messages) or ""
        recent = _recent_turn_summaries(messages)
        path = self.jev.route_turn(user_message, recent, last_topic or None)
        _log.info("Jev route=%s for message=%r", path, user_message[:80])
        # Clear prior-turn table so UI only shows this turn's results
        return {
            "route": path,
            "last_topic": last_topic,
            "search_results": [],
            "search_total": 0,
        }

    def _after_route(self, state: AgentState) -> Literal["clarify", "search", "chitchat"]:
        route = state.get("route") or "chitchat"
        if route == "clarify":
            return "clarify"
        if route == "search":
            return "search"
        return "chitchat"

    def _clarify_node(self, state: AgentState) -> dict:
        messages = [SystemMessage(content=CLARIFY_SYSTEM_PROMPT)] + list(state["messages"])
        response = self.llm.invoke(messages)
        return {"messages": [response]}

    def _chitchat_node(self, state: AgentState) -> dict:
        messages = [SystemMessage(content=CHITCHAT_SYSTEM_PROMPT)] + list(state["messages"])
        response = self.llm.invoke(messages)
        return {"messages": [response]}

    def _extract_node(self, state: AgentState) -> dict:
        messages = [SystemMessage(content=EXTRACT_SYSTEM_PROMPT)] + list(state["messages"])
        response = self.llm_with_tools.invoke(messages)
        updates: dict = {"messages": [response]}
        topic = _infer_topic_from_tool_calls([response])
        if topic:
            updates["last_topic"] = topic
        return updates

    def _after_extract(self, state: AgentState) -> Literal["tools", "end"]:
        last = state["messages"][-1]
        if hasattr(last, "tool_calls") and last.tool_calls:
            return "tools"
        return "end"

    def _tools_node(self, state: AgentState) -> dict:
        """Run library search, keep structured rows for the UI, text for the LLM."""
        last = state["messages"][-1]
        tool_calls = getattr(last, "tool_calls", None) or []
        tool_messages: list[ToolMessage] = []
        rows: list[dict] = []
        total = 0

        for tc in tool_calls:
            args = _tool_call_args(tc)
            call_id = _tool_call_id(tc)
            try:
                payload = run_library_search(
                    query=str(args.get("query") or ""),
                    resource_type=args.get("resource_type"),
                    date_from=args.get("date_from"),
                    date_to=args.get("date_to"),
                    limit=int(args.get("limit") or 10),
                )
                tool_messages.append(
                    ToolMessage(content=payload["text"], tool_call_id=call_id)
                )
                rows = payload.get("rows") or []
                total = int(payload.get("total") or 0)
            except Exception as e:
                _log.exception("Library tool failed")
                tool_messages.append(
                    ToolMessage(content=f"Error searching library: {e}", tool_call_id=call_id)
                )

        return {
            "messages": tool_messages,
            "search_results": rows,
            "search_total": total,
        }

    def _present_node(self, state: AgentState) -> dict:
        messages = [SystemMessage(content=PRESENT_SYSTEM_PROMPT)] + list(state["messages"])
        response = self.llm.invoke(messages)
        return {"messages": [response]}

    def _prepare_input(
        self, user_input: str, thread_id: str
    ) -> tuple[dict, dict]:
        """Build graph input state and config for a turn."""
        config = {"configurable": {"thread_id": thread_id}}
        input_state: dict = {
            "messages": [HumanMessage(content=user_input)],
            "route": "",
            "search_results": [],
            "search_total": 0,
        }
        try:
            snapshot = self.app.get_state(config)
            if snapshot and snapshot.values:
                prior_topic = snapshot.values.get("last_topic") or ""
                if prior_topic:
                    input_state["last_topic"] = prior_topic
        except Exception:
            _log.debug("No prior state for thread %s", thread_id)
        return input_state, config

    @staticmethod
    def _reply_from_state(result: dict) -> ChatReply:
        messages = result.get("messages") or []
        response = ""
        if messages:
            final = messages[-1]
            if isinstance(final, AIMessage):
                response = (final.content or "").strip()
            else:
                response = str(final).strip()

        rows = list(result.get("search_results") or [])
        total = int(result.get("search_total") or 0)
        if not response and rows:
            response = f"Found {total} resources (showing {len(rows)})."
        return ChatReply(text=response, results=rows, total=total)

    # Human-readable labels for Streamlit progress UI
    NODE_STATUS: dict[str, str] = {
        "route": "Deciding how to handle your request…",
        "extract": "Extracting search parameters…",
        "tools": "Searching the CSUSB library…",
        "present": "Summarizing results…",
        "clarify": "Preparing a clarifying question…",
        "chitchat": "Writing a reply…",
    }

    def chat_events(self, user_input: str, thread_id: str = "default"):
        """
        Stream progress events, then a final ChatReply.

        Yields:
            ("status", label: str) while nodes run
            ("done", ChatReply) when finished
            ("error", ChatReply) on failure
        """
        _log.info("Processing user input (thread: %s): %s...", thread_id, user_input[:100])
        try:
            input_state, config = self._prepare_input(user_input, thread_id)
            merged: dict = dict(input_state)
            yield ("status", "Starting…")

            for chunk in self.app.stream(input_state, config, stream_mode="updates"):
                if not isinstance(chunk, dict):
                    continue
                for node_name, update in chunk.items():
                    if isinstance(update, dict):
                        for key, value in update.items():
                            if key == "messages":
                                prev = list(merged.get("messages") or [])
                                merged["messages"] = prev + list(value)
                            else:
                                merged[key] = value

                    if node_name == "route":
                        route = (update or {}).get("route") if isinstance(update, dict) else None
                        if route == "search":
                            yield ("status", "Routing complete → library search")
                            yield ("status", "Extracting search parameters…")
                        elif route == "clarify":
                            yield ("status", "Routing complete → clarifying question")
                            yield ("status", "Drafting a clarifying question…")
                        else:
                            yield ("status", "Routing complete → general reply")
                            yield ("status", "Writing a reply…")
                    elif node_name == "extract":
                        yield ("status", "Search parameters ready")
                        yield ("status", "Searching the CSUSB library…")
                    elif node_name == "tools":
                        rows = (update or {}).get("search_results") or [] if isinstance(update, dict) else []
                        total = (update or {}).get("search_total") if isinstance(update, dict) else None
                        if rows:
                            yield (
                                "status",
                                f"Library search done — {total} found (showing {len(rows)})",
                            )
                        else:
                            yield ("status", "Library search done — no matching resources")
                        yield ("status", "Summarizing results…")
                    elif node_name == "present":
                        yield ("status", "Summary ready")
                    elif node_name == "clarify":
                        yield ("status", "Clarifying question ready")
                    elif node_name == "chitchat":
                        yield ("status", "Reply ready")
                    else:
                        yield ("status", self.NODE_STATUS.get(node_name, f"Working ({node_name})…"))

            reply = self._reply_from_state(merged)
            _log.info("Agent response: %s...", reply.text[:100])
            yield ("done", reply)
        except Exception as e:
            _log.exception("Error processing message")
            yield ("error", ChatReply(text=_user_facing_error(e)))

    def chat(self, user_input: str, thread_id: str = "default") -> ChatReply:
        """Process a user message and return text plus optional result table rows."""
        reply = ChatReply(text="")
        for kind, payload in self.chat_events(user_input, thread_id):
            if kind in ("done", "error"):
                reply = payload
        return reply


def create_scholar_agent() -> ScholarAgent:
    """Factory used by the Streamlit app."""
    return ScholarAgent()
