"""Text similarity between skills and CV phrases.

minilm  sentence-transformers all-MiniLM-L6-v2 on CPU, cosine of normalised
        embeddings. Skill embeddings are cached in data/cache/.
lexical word-overlap (Jaccard on light-stemmed words). No model download;
        deterministic, used by tests and as a fallback.
"""
from __future__ import annotations

import hashlib
import os
import re
import threading
from functools import cached_property
from pathlib import Path

import numpy as np

from .config import ROOT

CACHE = ROOT / "data" / "cache"
STOP = {"a", "an", "and", "the", "of", "to", "for", "in", "on", "with", "or", "by", "at", "as", "use",
        "using", "i", "my", "me", "we", "our", "from", "into", "about", "is", "are", "be", "s"}


def _stem(w: str) -> str:
    for suf in ("ing", "ies", "ied", "ed", "es", "s"):
        if len(w) > len(suf) + 2 and w.endswith(suf):
            return w[: -len(suf)] + ("y" if suf in ("ies", "ied") else "")
    return w


def tokens(text: str) -> frozenset[str]:
    return frozenset(_stem(w) for w in re.findall(r"[a-z0-9]+", text.lower()) if w not in STOP)


class Similarity:
    """Similarity over a fixed skill vocabulary (uri -> label, alt labels)."""

    def __init__(self, labels: dict[str, str], alt_labels: dict[str, list[str]], backend: str = "minilm",
                 model_name: str = "sentence-transformers/all-MiniLM-L6-v2"):
        self.labels = labels
        self.alt = alt_labels
        self.backend = backend
        self.model_name = model_name
        self._lock = threading.RLock()
        self._model = None
        self._emb: dict[str, np.ndarray] = {}
        self.uris = list(labels)
        self.pos = {u: i for i, u in enumerate(self.uris)}
        # all surface forms: label + alt labels, with the owning skill index
        forms, owner = [], []
        for u in self.uris:
            for f in [labels[u], *alt_labels.get(u, [])]:
                forms.append(f)
                owner.append(self.pos[u])
        self.forms, self.owner = forms, np.array(owner)

    # ---------- backends ----------
    def _get_model(self):
        with self._lock:
            if self._model is None:
                from sentence_transformers import SentenceTransformer
                self._model = SentenceTransformer(self.model_name, device="cpu")
            return self._model

    def _embed(self, texts: list[str]) -> np.ndarray:
        return np.asarray(self._get_model().encode(texts, batch_size=128, normalize_embeddings=True,
                                                   show_progress_bar=False), dtype=np.float32)

    def _cached(self, name: str, texts: list[str]) -> np.ndarray:
        """Embeddings of `texts`, computed once and kept in memory and in data/cache/."""
        with self._lock:  # requests arrive in parallel: load the model and write the cache once
            if name in self._emb:
                return self._emb[name]
            key = hashlib.sha1((self.model_name + "\n" + "\n".join(texts)).encode("utf-8")).hexdigest()[:16]
            path = CACHE / f"{name}_{key}.npy"
            if path.exists():
                emb = np.load(path)
            else:
                emb = self._embed(texts)
                CACHE.mkdir(parents=True, exist_ok=True)
                tmp = path.with_name(f"{path.stem}.{os.getpid()}.tmp.npy")
                np.save(tmp, emb)
                os.replace(tmp, path)
            self._emb[name] = emb
            return emb

    @property
    def _label_emb(self) -> np.ndarray:
        return self._cached("skill_labels", [self.labels[u] for u in self.uris])

    @property
    def _form_emb(self) -> np.ndarray:
        return self._cached("skill_forms", self.forms)

    @cached_property
    def _label_tok(self) -> list[frozenset[str]]:
        return [tokens(self.labels[u]) for u in self.uris]

    @cached_property
    def _form_tok(self) -> list[frozenset[str]]:
        return [tokens(f) for f in self.forms]

    @staticmethod
    def _jaccard(a: list[frozenset[str]], b: list[frozenset[str]]) -> np.ndarray:
        out = np.zeros((len(a), len(b)), dtype=np.float32)
        for i, x in enumerate(a):
            for j, y in enumerate(b):
                if x and y:
                    out[i, j] = len(x & y) / len(x | y)
        return out

    # ---------- public ----------
    def skills(self, a: list[str], b: list[str]) -> np.ndarray:
        """len(a) x len(b) similarity between skills (by label)."""
        if self.backend == "lexical":
            return self._jaccard([self._label_tok[self.pos[u]] for u in a], [self._label_tok[self.pos[u]] for u in b])
        ea = self._label_emb[[self.pos[u] for u in a]]
        eb = self._label_emb[[self.pos[u] for u in b]]
        return np.clip(ea @ eb.T, 0.0, 1.0)

    def phrases(self, phrases: list[str], candidates: list[str]) -> np.ndarray:
        """len(phrases) x len(candidates): best match of each phrase to any form of each skill."""
        cand = np.array([self.pos[u] for u in candidates])
        keep = np.isin(self.owner, cand)
        if self.backend == "lexical":
            sims = self._jaccard([tokens(p) for p in phrases], [t for t, k in zip(self._form_tok, keep) if k])
        else:
            sims = np.clip(self._embed(phrases) @ self._form_emb[keep].T, 0.0, 1.0)
        owners = self.owner[keep]
        col = {p: i for i, p in enumerate(cand)}
        out = np.zeros((len(phrases), len(candidates)), dtype=np.float32)
        for j, o in enumerate(owners):
            c = col[o]
            out[:, c] = np.maximum(out[:, c], sims[:, j])
        return out
