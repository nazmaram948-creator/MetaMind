"""One small interface for the optional LLM.

The LLM may only (a) pull skill phrases out of CV text and (b) word explanations
from IDs and numbers we pass in. It never chooses jobs, courses or statistics:
whatever it returns is matched against the database and anything unknown is dropped.

LLM_PROVIDER=none (default) disables it; the engine then splits CV text itself
and uses template explanations. Providers are added here behind the same two
functions, reading their key from the environment (.env), never from the repo.
"""
from __future__ import annotations

import os


class NoLLM:
    name = "none"

    def extract_skill_phrases(self, text: str) -> list[str] | None:
        return None

    def explain(self, facts: dict) -> str | None:
        return None


def get_llm():
    provider = os.environ.get("LLM_PROVIDER", "none").strip().lower()
    if provider in ("", "none"):
        return NoLLM()
    raise NotImplementedError(f"LLM provider {provider!r} is not wired yet; set LLM_PROVIDER=none")
