"""Transparent text-matching utilities shared by every condition.

Both the provenance observer and *both* reconstructors use these functions. That
is deliberate: if the conditions differ, it must be because of the telemetry
available to them, not because one of them got a better matching algorithm.

Everything here is plain string work. No model, no ML, no heuristics beyond what
is written on the page.
"""

from __future__ import annotations

import re

#: Tokens we consider identifying: long enough that a coincidental match between
#: an untrusted document and a later tool argument is unlikely.
MIN_SIGNIFICANT_TOKEN = 8

_TOKEN_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9._\-/]{2,}")

#: Imperative instruction shapes that may appear in retrieved content. Content
#: matching these is *not* assumed malicious; it is flagged as an instruction-like
#: span inside data, which is an observable property of the content itself.
_INSTRUCTION_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"INSTRUCTION[S]?\b.*", re.IGNORECASE),
    re.compile(r"\bignore (?:the|your|all|previous|prior)\b.*", re.IGNORECASE),
    re.compile(r"\bdisregard (?:the|your|all|previous|prior)\b.*", re.IGNORECASE),
    re.compile(r"\byou must (?:now )?(?:use|call|invoke|create|delete|fetch)\b.*", re.IGNORECASE),
)


def tokens(text: str, min_length: int = MIN_SIGNIFICANT_TOKEN) -> set[str]:
    """Identifier-like tokens of at least ``min_length`` characters.

    Trailing punctuation is stripped so that ``demo-admin-svc.`` at the end of a
    sentence matches ``demo-admin-svc`` in a later argument.
    """
    found = (t.strip("._-/") for t in _TOKEN_RE.findall(text or ""))
    return {t for t in found if len(t) >= min_length}


def shared_significant_tokens(
    source_text: str, target_text: str, min_length: int = MIN_SIGNIFICANT_TOKEN
) -> set[str]:
    """Identifying tokens present in both texts.

    A non-empty result supports the defensible statement "this exact string is
    present both in the earlier content and in the later event" - never the
    statement that the earlier content caused the later event.
    """
    return tokens(source_text, min_length) & tokens(target_text, min_length)


def detect_instruction_spans(text: str) -> list[str]:
    """Instruction-shaped spans found inside content.

    Observable property of the retrieved data, computed identically for both
    observation conditions.
    """
    spans: list[str] = []
    for line in (text or "").splitlines():
        stripped = line.strip()
        for pattern in _INSTRUCTION_PATTERNS:
            match = pattern.search(stripped)
            if match:
                spans.append(match.group(0).strip())
                break
    return spans


def mentions(text: str, needle: str | None) -> bool:
    """Case-insensitive containment of a non-trivial identifier."""
    if not needle or len(needle) < 4:
        return False
    return needle.lower() in (text or "").lower()
