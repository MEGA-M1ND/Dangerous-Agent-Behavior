"""Recording and importing investigator responses.

Timing is measured only where it can be: an explicit ``start`` before the work
and a ``submit`` afterwards. If no start record exists, the response is marked
``timing_is_reliable: false`` and its duration is not used in any timing summary.
The experiment does not pretend to know how long an investigator spent if it was
never told.

Mock-investigator responses are written under ``responses/_mock`` and are never
loaded by the real-response reader. They exist to test the pipeline, not to
produce evidence.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from experiment2.questionnaire import InvestigatorResponse

MOCK_NAMESPACE = "_mock"
LLM_NAMESPACE_PREFIX = "llm_"


def responses_dir(root: Path) -> Path:
    return Path(root) / "responses"


def _participant_dir(root: Path, participant_id: str) -> Path:
    path = responses_dir(root) / participant_id
    path.mkdir(parents=True, exist_ok=True)
    return path


def start(root: Path, participant_id: str, packet_id: str) -> Path:
    """Record that an investigator has opened a packet and begun work."""
    now = datetime.now(timezone.utc)
    path = _participant_dir(root, participant_id) / f"{packet_id}.start.json"
    path.write_text(
        json.dumps(
            {"participant_id": participant_id, "packet_id": packet_id, "started_at": now.isoformat()},
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    return path


def _read_start(root: Path, participant_id: str, packet_id: str) -> datetime | None:
    path = responses_dir(root) / participant_id / f"{packet_id}.start.json"
    if not path.exists():
        return None
    return datetime.fromisoformat(json.loads(path.read_text(encoding="utf-8"))["started_at"])


def submit(
    root: Path,
    answers: dict[str, Any],
    participant_id: str | None = None,
    submitted_at: datetime | None = None,
) -> InvestigatorResponse:
    """Validate and store one completed questionnaire."""
    payload = dict(answers)
    if participant_id:
        payload["participant_id"] = participant_id
    payload.setdefault("investigator_kind", "human")

    started = _read_start(root, payload["participant_id"], payload["packet_id"])
    finished = submitted_at or datetime.now(timezone.utc)
    if started is not None:
        payload.setdefault("started_at", started)
        payload["duration_seconds"] = round((finished - started).total_seconds(), 3)
        payload["timing_is_reliable"] = True
    else:
        payload.setdefault("timing_is_reliable", False)
    payload.setdefault("submitted_at", finished)

    response = InvestigatorResponse.model_validate(payload)
    path = _participant_dir(root, response.participant_id) / f"{response.packet_id}.json"
    path.write_text(response.model_dump_json(indent=2) + "\n", encoding="utf-8")
    return response


def import_file(root: Path, answers_path: Path, participant_id: str | None = None) -> InvestigatorResponse:
    return submit(root, json.loads(Path(answers_path).read_text(encoding="utf-8")), participant_id)


def store_response(root: Path, response: InvestigatorResponse, namespace: str) -> Path:
    """Write a generated response (mock or model) into its own namespace."""
    directory = responses_dir(root) / namespace / response.participant_id
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / f"{response.packet_id}.json"
    path.write_text(response.model_dump_json(indent=2) + "\n", encoding="utf-8")
    return path


def load_responses(root: Path, include_mock: bool = False) -> list[InvestigatorResponse]:
    """All stored responses.

    Mock responses are excluded unless explicitly requested, so that a pipeline
    test can never be mistaken for study evidence.
    """
    directory = responses_dir(root)
    if not directory.exists():
        return []
    responses: list[InvestigatorResponse] = []
    for path in sorted(directory.rglob("*.json")):
        if path.name.endswith(".start.json"):
            continue
        if MOCK_NAMESPACE in path.parts and not include_mock:
            continue
        response = InvestigatorResponse.model_validate_json(path.read_text(encoding="utf-8"))
        if response.investigator_kind == "mock" and not include_mock:
            continue
        responses.append(response)
    return responses


def response_counts(root: Path) -> dict[str, int]:
    counts = {"human": 0, "llm": 0, "mock": 0}
    for response in load_responses(root, include_mock=True):
        counts[response.investigator_kind] = counts.get(response.investigator_kind, 0) + 1
    return counts
