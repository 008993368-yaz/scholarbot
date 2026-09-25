# core/clients/jev_client.py
"""OpenRouter Decisions API client for TypeSafe Jev (~typesafe/jev-latest)."""
from __future__ import annotations

import os
from typing import Any, Dict, Optional

import requests

from core.utils.logging_utils import get_logger

_log = get_logger(__name__)

DECISIONS_URL = "https://openrouter.ai/api/alpha/decisions"
DEFAULT_JEV_MODEL = "~typesafe/jev-latest"
HAS_TOPIC_THRESHOLD = 0.55

ROUTE_QUESTIONS: Dict[str, Any] = {
    "action": {
        "type": "choice",
        "instructions": (
            "Given the user's latest message and conversation context, what should "
            "ScholarBot do next?"
        ),
        "criteria": {
            "search": (
                "The user wants library resources and a searchable research topic "
                "is present in this message or prior turns (including refinements "
                "like 'only books from 2023')."
            ),
            "clarify": (
                "The user wants a library search but the topic is missing, author-only, "
                "or too vague to search without asking a clarifying question."
            ),
            "chitchat": (
                "Greetings, thanks, help about how ScholarBot works, or other "
                "non-search conversation."
            ),
        },
    },
    "has_topic": {
        "type": "noul",
        "instructions": (
            "Is there a searchable research topic (keywords or subject area) in the "
            "latest message or conversation history?"
        ),
        "criteria": {
            "true": "A concrete topic, keywords, or subject is available to search.",
            "false": "No usable research topic; only author, vague intent, or chitchat.",
        },
    },
}


class JevClient:
    """Thin wrapper around OpenRouter Decisions API for Jev routing decisions."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: Optional[str] = None,
        timeout: int = 30,
    ):
        self.api_key = api_key or os.getenv("OPENROUTER_API_KEY", "")
        self.model = model or os.getenv("JEV_MODEL", DEFAULT_JEV_MODEL)
        self.timeout = timeout
        if not self.api_key:
            raise ValueError(
                "OPENROUTER_API_KEY is required for Jev decisions. "
                "Set it in your .env file (https://openrouter.ai/settings/keys)."
            )

    def decide(self, state: Any, questions: Dict[str, Any]) -> Dict[str, Any]:
        """
        Call Jev with application state and typed questions.

        Returns the `answers` object from the Decisions API response.
        """
        payload = {
            "model": self.model,
            "state": state,
            "questions": questions,
        }
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://github.com/scholarbot",
            "X-Title": "ScholarBot",
        }
        _log.info("Calling Jev Decisions API model=%s", self.model)
        response = requests.post(
            DECISIONS_URL,
            headers=headers,
            json=payload,
            timeout=self.timeout,
        )
        response.raise_for_status()
        data = response.json()
        answers = data.get("answers") or {}
        _log.info("Jev answers: %s", answers)
        return answers

    def route_turn(
        self,
        user_message: str,
        recent_turns: list[str],
        last_topic: Optional[str] = None,
    ) -> str:
        """
        Decide the graph path for this turn: search | clarify | chitchat.

        Applies the plan's deterministic thresholds on Jev's typed answers.
        """
        state = {
            "user_message": user_message,
            "recent_turns": recent_turns[-6:],
            "last_topic": last_topic or "",
        }
        try:
            answers = self.decide(state, ROUTE_QUESTIONS)
        except Exception:
            _log.exception("Jev routing failed; falling back to heuristic")
            return self._fallback_route(user_message, last_topic)

        action_ans = answers.get("action") or {}
        action = (action_ans.get("choice") or "chitchat").lower()
        has_topic = float((answers.get("has_topic") or {}).get("noul") or 0.0)

        if action == "clarify" or (action == "search" and has_topic < HAS_TOPIC_THRESHOLD):
            return "clarify"
        if action == "search" and has_topic >= HAS_TOPIC_THRESHOLD:
            return "search"
        return "chitchat"

    @staticmethod
    def _fallback_route(user_message: str, last_topic: Optional[str]) -> str:
        """Simple keyword fallback if Jev is unavailable."""
        text = (user_message or "").strip().lower()
        if not text:
            return "clarify"
        greetings = ("hi", "hello", "hey", "thanks", "thank you", "help", "what can you")
        if any(text.startswith(g) or text == g for g in greetings) and len(text.split()) <= 6:
            return "chitchat"
        refine_words = ("only", "from", "between", "books", "articles", "recent", "more")
        if last_topic and any(w in text for w in refine_words):
            return "search"
        if len(text.split()) < 2 and not last_topic:
            return "clarify"
        return "search"
