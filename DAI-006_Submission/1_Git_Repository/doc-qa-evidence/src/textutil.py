"""Small text helpers: tokenising, light stemming, keyword extraction, sentence split."""
from __future__ import annotations

import re

STOPWORDS = frozenset(
    """a an the and or but if of to in on at by for with from as into over within about
    is are was were be been being am do does did doing have has had having can could may
    might must shall should will would i me my we our you your he she it its they them their
    this that these those what which who whom whose when where why how many much get gets got
    there here per any some than then so not no yes also very just""".split()
)

_TOKEN = re.compile(r"[a-z0-9]+")


def tokenize(text: str) -> list[str]:
    return _TOKEN.findall(text.lower())


def stem(token: str) -> str:
    """Very light suffix stripping so 'days'/'day' and 'reimbursed'/'reimburse' match."""
    t = token
    if len(t) <= 3 or t.isdigit():
        return t
    rules = (("ies", "y"), ("ied", "y"), ("sses", "ss"), ("ches", "ch"), ("shes", "sh"),
             ("xes", "x"), ("ing", ""), ("ed", ""), ("ly", ""))
    for suffix, repl in rules:
        if t.endswith(suffix) and len(t) - len(suffix) >= 3:
            t = t[: -len(suffix)] + repl
            break
    else:
        if t.endswith("s") and not t.endswith("ss") and len(t) > 3:
            t = t[:-1]
    if t.endswith("e") and len(t) > 4:
        t = t[:-1]
    return t


def keywords(question: str) -> list[str]:
    """Unique, non-stopword tokens of the question, in order."""
    seen: list[str] = []
    for tok in tokenize(question):
        if tok in STOPWORDS or (len(tok) < 2 and not tok.isdigit()):
            continue
        if tok not in seen:
            seen.append(tok)
    return seen


def stem_set(text: str) -> set[str]:
    return {stem(t) for t in tokenize(text)}


def split_sentences(text: str) -> list[str]:
    """Split into sentences; markdown headings are skipped (poor answers on their own)."""
    out: list[str] = []
    for line in text.split("\n"):
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        line = line.lstrip("-*• ").strip()
        out.extend(s.strip() for s in re.split(r"(?<=[.!?])\s+", line) if s.strip())
    return out
