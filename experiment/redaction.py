"""Credential redaction and argument sanitization.

All credentials in this experiment are synthetic strings, but they are treated as
if they were real: a raw credential value must never reach any log file, any
report, or any reconstruction artifact.

Two representations exist, and the difference between them is part of the
experimental manipulation:

``BASELINE_REDACTION``
    ``"***REDACTED***"`` - conventional sanitization. It removes the value *and*
    the join key, so a conventional log cannot tell which credential flowed into
    which later call.

``credential_reference``
    ``cred://<name>#<sha256[:12]>`` - a stable, non-reversible reference recorded
    by the provenance observer in a dedicated field. It carries no secret
    material but preserves identity across events.
"""

from __future__ import annotations

import hashlib
import re
from typing import Any, Iterable

BASELINE_REDACTION = "***REDACTED***"

#: Argument names whose values are always treated as secret material.
SECRET_ARG_NAMES: frozenset[str] = frozenset(
    {"token", "secret", "password", "api_key", "apikey", "credential", "auth", "key"}
)

#: Shape of every synthetic credential minted by the mock secret store.
SYNTHETIC_SECRET_PATTERN = re.compile(r"SYNTHETIC-[A-Z0-9_]+-[a-f0-9]{8}")


def credential_reference(name: str, value: str) -> str:
    """An opaque, stable reference to a credential. Never reversible."""
    digest = hashlib.sha256(value.encode("utf-8")).hexdigest()[:12]
    return f"cred://{name}#{digest}"


def looks_like_secret(value: Any) -> bool:
    return isinstance(value, str) and bool(SYNTHETIC_SECRET_PATTERN.search(value))


def sanitize_arguments(arguments: dict[str, Any]) -> dict[str, Any]:
    """Return arguments safe to log, in the conventional style.

    Values are redacted when the argument name suggests a credential or when the
    value itself matches the synthetic-secret shape. The redaction is identical in
    both conditions: the provenance stream gains credential identity through the
    dedicated ``credential_reference`` field, not through richer arguments.
    """
    safe: dict[str, Any] = {}
    for key, value in arguments.items():
        if key.lower() in SECRET_ARG_NAMES or looks_like_secret(value):
            safe[key] = BASELINE_REDACTION
        elif isinstance(value, dict):
            safe[key] = sanitize_arguments(value)
        elif isinstance(value, (list, tuple)):
            safe[key] = [
                BASELINE_REDACTION if looks_like_secret(v) else v for v in value
            ]
        else:
            safe[key] = value
    return safe


def scrub_text(text: str) -> str:
    """Remove any synthetic secret material appearing inside free text."""
    return SYNTHETIC_SECRET_PATTERN.sub(BASELINE_REDACTION, text)


def contains_secret(blob: str, secrets: Iterable[str]) -> bool:
    return any(secret and secret in blob for secret in secrets)
