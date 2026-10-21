"""CV / free text -> ESCO skill candidates.

1. Remove personal data we must never use (age, gender, date of birth, NRIC,
   e-mail, phone).
2. Phrases: from the LLM when one is configured, otherwise lines, sentences and
   comma-separated parts of the text.
3. Each phrase is compared with every surface form (label + alternative labels)
   of the skills attached to our target occupations. A skill's confidence is its
   best phrase score: >= auto_suggest is "suggested", otherwise "needs_confirmation".
"""
from __future__ import annotations

import re

import numpy as np

from .llm import get_llm
from .similarity import Similarity

PII = [
    re.compile(r"\b(?:age|aged|umur)\s*[:=]?\s*\d{1,3}\b", re.I),
    re.compile(r"\b\d{1,3}\s*(?:years?\s*old|y/?o)\b", re.I),
    re.compile(r"\b(?:gender|sex|jantina)\s*[:=]?\s*\w+", re.I),
    re.compile(r"\b(?:date of birth|dob|born)\s*[:=]?\s*[\w/ .-]{0,20}\d", re.I),
    re.compile(r"\b\d{6}-\d{2}-\d{4}\b"),                   # NRIC
    re.compile(r"[\w.+-]+@[\w-]+\.[\w.]+"),                 # e-mail
    re.compile(r"(?:\+?60|0)1\d[- ]?\d{3,4}[- ]?\d{4}\b"),  # MY mobile
]
BULLET = re.compile(r"^\s*(?:[-*•·▪]|\d+[.)])\s*")
MAX_WORDS = 25


def strip_pii(text: str) -> str:
    for p in PII:
        text = p.sub(" ", text)
    return text


def split_phrases(text: str) -> list[str]:
    out: list[str] = []
    for line in text.splitlines():
        line = BULLET.sub("", line).strip()
        for clause in re.split(r"(?<=[.!?;])\s+|;", line):
            clause = clause.strip(" .;:")
            if not clause:
                continue
            parts = [clause] + [p.strip(" .") for p in re.split(r",|\band\b|\(|\)", clause)]
            for p in parts:
                words = p.split()
                if 1 <= len(words) <= MAX_WORDS and len(p) >= 3 and p not in out:
                    out.append(p)
    return out


def parse(text: str, sim: Similarity, candidates: list[str], *, auto_suggest: float,
          min_candidate: float, max_per_phrase: int, max_results: int = 30) -> list[dict]:
    clean = strip_pii(text)
    phrases = get_llm().extract_skill_phrases(clean) or split_phrases(clean)
    if not phrases or not candidates:
        return []
    scores = sim.phrases(phrases, candidates)               # phrases x candidates
    best: dict[str, tuple[float, str]] = {}
    for i, phrase in enumerate(phrases):
        row = scores[i]
        for j in np.argsort(-row)[:max_per_phrase]:
            conf = float(row[j])
            if conf < min_candidate:
                break
            uri = candidates[j]
            if uri not in best or conf > best[uri][0]:
                best[uri] = (conf, phrase)
    out = [{"skill_id": uri, "skill_name": sim.labels[uri], "extracted_phrase": phrase,
            "confidence": round(conf, 3),
            "status": "suggested" if conf >= auto_suggest else "needs_confirmation"}
           for uri, (conf, phrase) in best.items()]
    return sorted(out, key=lambda d: (-d["confidence"], d["skill_name"]))[:max_results]
