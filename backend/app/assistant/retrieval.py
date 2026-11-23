"""Knowledge-base retrieval for VigilAI (safeguard layer 2: restricted knowledge).

The knowledge base is a small set of Markdown files maintained with the code
(``knowledge_base/``).  Documents are split into heading-based chunks and
ranked with BM25 keyword scoring implemented here in plain Python.

A vector database is deliberately not used: the corpus is a few dozen chunks,
queries are dominated by exact domain terms (``SEC-001``, ``Alertmanager``),
and lexical ranking is deterministic, explainable and has no extra service to
operate.
"""
from __future__ import annotations

import math
import re
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from app.core.config import settings

_TOKEN = re.compile(r"[a-z]+-\d+|[a-z0-9]+")
_STOPWORDS = frozenset(
    """a an and are as at be been but by can could do does did for from had has have how i if in into
    is it its me my of on or our should so than that the their them then there these they this to was
    we were what when where which who why will with would you your about tell show please explain
    describe give list""".split()
)
MAX_CHUNK_CHARS = 1500
K1 = 1.5
B = 0.75
MIN_SCORE = 1.2
RELATIVE_CUTOFF = 0.45


def tokenize(text: str) -> List[str]:
    tokens = []
    for raw in _TOKEN.findall(text.lower()):
        if raw in _STOPWORDS:
            continue
        # light plural/verb normalisation: incidents -> incident, findings -> finding
        if len(raw) > 4 and raw.endswith("ies"):
            raw = raw[:-3] + "y"
        elif len(raw) > 3 and raw.endswith("s") and not raw.endswith("ss") and not raw[-2].isdigit():
            raw = raw[:-1]
        tokens.append(raw)
    return tokens


@dataclass(frozen=True)
class Chunk:
    document: str  # file name
    title: str     # document title (H1)
    section: str   # section heading (H2/H3)
    text: str

    @property
    def reference(self) -> str:
        return f"{self.title} › {self.section}" if self.section else self.title


def _split_long(text: str) -> List[str]:
    if len(text) <= MAX_CHUNK_CHARS:
        return [text]
    parts: List[str] = []
    current = ""
    for paragraph in re.split(r"\n\s*\n", text):
        if current and len(current) + len(paragraph) + 2 > MAX_CHUNK_CHARS:
            parts.append(current.strip())
            current = ""
        current += paragraph + "\n\n"
    if current.strip():
        parts.append(current.strip())
    return parts


def chunk_markdown(document: str, markdown: str) -> List[Chunk]:
    title = document
    section = ""
    buffer: List[str] = []
    chunks: List[Chunk] = []

    def flush() -> None:
        text = "\n".join(buffer).strip()
        buffer.clear()
        if not text:
            return
        for part in _split_long(text):
            chunks.append(Chunk(document=document, title=title, section=section, text=part))

    for line in markdown.splitlines():
        if line.startswith("# ") and not line.startswith("## "):
            flush()
            title = line[2:].strip()
            section = ""
        elif line.startswith("## ") or line.startswith("### "):
            flush()
            section = line.lstrip("#").strip()
        else:
            buffer.append(line)
    flush()
    return chunks


class KnowledgeBase:
    """In-memory BM25 index over the Markdown knowledge base."""

    def __init__(self, directory: Path) -> None:
        self.directory = directory
        self.chunks: List[Chunk] = []
        self._term_freqs: List[Dict[str, int]] = []
        self._lengths: List[int] = []
        self._doc_freq: Dict[str, int] = {}
        self._avg_len = 0.0
        self._signature: Tuple = ()
        self._lock = threading.Lock()
        self.reload()

    def _scan_signature(self) -> Tuple:
        if not self.directory.is_dir():
            return ()
        return tuple(
            sorted((p.name, p.stat().st_mtime_ns, p.stat().st_size) for p in self.directory.glob("*.md"))
        )

    def reload(self) -> None:
        with self._lock:
            signature = self._scan_signature()
            chunks: List[Chunk] = []
            if self.directory.is_dir():
                for path in sorted(self.directory.glob("*.md")):
                    try:
                        chunks.extend(chunk_markdown(path.name, path.read_text(encoding="utf-8")))
                    except (OSError, UnicodeDecodeError):
                        continue
            self.chunks = chunks
            self._term_freqs = []
            self._lengths = []
            self._doc_freq = {}
            for chunk in chunks:
                # Heading terms are weighted more heavily than body terms.
                tokens = tokenize(chunk.text) + tokenize(chunk.section) * 3 + tokenize(chunk.title)
                freqs: Dict[str, int] = {}
                for token in tokens:
                    freqs[token] = freqs.get(token, 0) + 1
                self._term_freqs.append(freqs)
                self._lengths.append(len(tokens))
                for token in freqs:
                    self._doc_freq[token] = self._doc_freq.get(token, 0) + 1
            self._avg_len = (sum(self._lengths) / len(self._lengths)) if self._lengths else 0.0
            self._signature = signature

    def refresh_if_changed(self) -> None:
        if self._scan_signature() != self._signature:
            self.reload()

    def search(self, query: str, limit: int = 4) -> List[Tuple[Chunk, float]]:
        terms = tokenize(query)
        if not terms or not self.chunks:
            return []
        total = len(self.chunks)
        scored: List[Tuple[Chunk, float]] = []
        for index, chunk in enumerate(self.chunks):
            freqs = self._term_freqs[index]
            length = self._lengths[index] or 1
            score = 0.0
            for term in set(terms):
                frequency = freqs.get(term)
                if not frequency:
                    continue
                doc_freq = self._doc_freq.get(term, 0)
                idf = math.log(1 + (total - doc_freq + 0.5) / (doc_freq + 0.5))
                norm = frequency * (K1 + 1) / (frequency + K1 * (1 - B + B * length / self._avg_len))
                score += idf * norm
            if score > 0:
                scored.append((chunk, score))
        scored.sort(key=lambda item: item[1], reverse=True)
        if not scored or scored[0][1] < MIN_SCORE:
            return []
        cutoff = max(MIN_SCORE, scored[0][1] * RELATIVE_CUTOFF)
        return [item for item in scored[:limit] if item[1] >= cutoff]

    def topics(self) -> List[Dict[str, str]]:
        seen: Dict[str, str] = {}
        for chunk in self.chunks:
            seen.setdefault(chunk.document, chunk.title)
        return [{"document": doc, "title": title} for doc, title in sorted(seen.items())]


_kb: Optional[KnowledgeBase] = None
_kb_lock = threading.Lock()


def get_knowledge_base() -> KnowledgeBase:
    global _kb
    with _kb_lock:
        if _kb is None:
            _kb = KnowledgeBase(settings.knowledge_base_path)
        else:
            _kb.refresh_if_changed()
        return _kb
