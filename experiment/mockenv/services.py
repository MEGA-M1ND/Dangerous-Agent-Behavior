"""Mock services: browser, filesystem, secret store, cloud, memory.

Every operation is synthetic. The "dangerous" operations mutate an in-memory
dictionary belonging to this object and nothing else. The filesystem tool is
confined to a repository-local sandbox directory created for the run.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal

from experiment.ids import short_hash
from experiment.mockenv.documents import CORPORA, MEMORY_SEEDS, Document
from experiment.mockenv.registry import (
    BASE_PERMISSIONS,
    CREDENTIAL_GRANTS,
    TOOL_PERMISSION_REQUIREMENTS,
    TOOL_REGISTRY,
)


@dataclass
class ToolOutcome:
    """Result of one mock tool call, before any observation or redaction."""

    status: Literal["ok", "error", "denied"]
    payload: Any = None
    preview: str = ""
    target_resource: str | None = None
    error: str | None = None
    environment_changes: list[dict[str, Any]] = field(default_factory=list)
    credential_name: str | None = None
    external_resource: str | None = None
    granted_permissions: tuple[str, ...] = ()


def _synthetic_secret(name: str) -> str:
    """A clearly fake credential. Shape is matched by the redaction filter."""
    return f"SYNTHETIC-{name.upper().replace('-', '_')}-{short_hash('mock-secret::' + name, 8)}"


class MockEnvironment:
    """The whole synthetic world the agent can act on."""

    def __init__(
        self, sandbox_dir: Path, corpus: str = "clean", memory_seed: str = "empty"
    ) -> None:
        self.sandbox_dir = Path(sandbox_dir)
        self.sandbox_dir.mkdir(parents=True, exist_ok=True)
        self.corpus_name = corpus
        self.memory_seed_name = memory_seed
        self.documents: dict[str, Document] = CORPORA[corpus]
        # Memory may be pre-populated, standing in for state carried over from an
        # earlier run. Its contents are as untrustworthy as anything else the
        # agent reads back.
        self.memory: dict[str, str] = dict(MEMORY_SEEDS[memory_seed])
        self.secrets: dict[str, str] = {
            name: _synthetic_secret(name) for name in CREDENTIAL_GRANTS
        }
        self.cloud_services: dict[str, str] = {
            "demo-service": "HEALTHY",
            "demo-batch": "DEGRADED",
        }
        self.cloud_resources: dict[str, dict[str, Any]] = {
            "res-web-01": {"kind": "compute", "state": "running"},
            "res-db-01": {"kind": "database", "state": "running"},
        }
        self.cloud_users: dict[str, dict[str, Any]] = {}

    # -- introspection --------------------------------------------------------

    def synthetic_secret_values(self) -> list[str]:
        return list(self.secrets.values())

    def snapshot(self) -> dict[str, Any]:
        return {
            "cloud_services": dict(self.cloud_services),
            "cloud_resources": {k: dict(v) for k, v in self.cloud_resources.items()},
            "cloud_users": {k: dict(v) for k, v in self.cloud_users.items()},
            "memory_keys": sorted(self.memory),
            "sandbox_files": sorted(p.name for p in self.sandbox_dir.glob("*")),
        }

    # -- dispatch -------------------------------------------------------------

    def call(
        self, tool_name: str, arguments: dict[str, Any], permissions: tuple[str, ...]
    ) -> ToolOutcome:
        spec = TOOL_REGISTRY.get(tool_name)
        if spec is None:
            return ToolOutcome(status="error", error=f"unknown tool: {tool_name}")

        required = TOOL_PERMISSION_REQUIREMENTS.get(tool_name)
        if required and required not in permissions:
            return ToolOutcome(
                status="denied",
                error=f"missing permission: {required}",
                target_resource=arguments.get("username") or arguments.get("resource_id"),
            )

        handler = getattr(self, "_" + tool_name.replace(".", "_"), None)
        if handler is None:  # pragma: no cover - registry and handlers stay in sync
            return ToolOutcome(status="error", error=f"unimplemented tool: {tool_name}")
        return handler(arguments)

    # -- browser --------------------------------------------------------------

    def _browser_list_documents(self, arguments: dict[str, Any]) -> ToolOutcome:
        listing = [
            {"document_id": d.document_id, "title": d.title}
            for d in self.documents.values()
        ]
        return ToolOutcome(
            status="ok",
            payload=listing,
            preview=json.dumps(listing),
            target_resource="document_index",
            external_resource="local://documents",
        )

    def _browser_open_document(self, arguments: dict[str, Any]) -> ToolOutcome:
        document_id = str(arguments.get("document_id", ""))
        document = self.documents.get(document_id)
        if document is None:
            return ToolOutcome(
                status="error", error=f"no such document: {document_id}",
                target_resource=document_id,
            )
        return ToolOutcome(
            status="ok",
            payload=document.text,
            preview=document.text,
            target_resource=document_id,
            external_resource=f"local://documents/{document_id}",
        )

    # -- filesystem -----------------------------------------------------------

    def _resolve_sandbox(self, relative: str) -> Path:
        candidate = (self.sandbox_dir / relative).resolve()
        root = self.sandbox_dir.resolve()
        if root != candidate and root not in candidate.parents:
            raise ValueError(f"path escapes sandbox: {relative}")
        return candidate

    def _filesystem_read_file(self, arguments: dict[str, Any]) -> ToolOutcome:
        relative = str(arguments.get("path", ""))
        try:
            path = self._resolve_sandbox(relative)
            text = path.read_text(encoding="utf-8")
        except (ValueError, OSError) as exc:
            return ToolOutcome(status="error", error=str(exc), target_resource=relative)
        return ToolOutcome(status="ok", payload=text, preview=text, target_resource=relative)

    def _filesystem_write_file(self, arguments: dict[str, Any]) -> ToolOutcome:
        relative = str(arguments.get("path", ""))
        content = str(arguments.get("content", ""))
        try:
            path = self._resolve_sandbox(relative)
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content, encoding="utf-8")
        except (ValueError, OSError) as exc:
            return ToolOutcome(status="error", error=str(exc), target_resource=relative)
        return ToolOutcome(
            status="ok",
            payload={"path": relative, "bytes": len(content)},
            preview=f"wrote {len(content)} bytes to {relative}",
            target_resource=relative,
            environment_changes=[
                {"kind": "sandbox_file_written", "resource": relative, "bytes": len(content)}
            ],
        )

    # -- memory ---------------------------------------------------------------

    def _memory_read(self, arguments: dict[str, Any]) -> ToolOutcome:
        key = str(arguments.get("key", ""))
        if key not in self.memory:
            return ToolOutcome(status="error", error=f"no memory item: {key}", target_resource=key)
        value = self.memory[key]
        return ToolOutcome(status="ok", payload=value, preview=value, target_resource=key)

    def _memory_write(self, arguments: dict[str, Any]) -> ToolOutcome:
        key = str(arguments.get("key", ""))
        value = str(arguments.get("value", ""))
        self.memory[key] = value
        return ToolOutcome(
            status="ok",
            payload={"key": key},
            preview=f"stored memory item {key}",
            target_resource=key,
            environment_changes=[{"kind": "memory_item_written", "resource": key}],
        )

    # -- secret store ---------------------------------------------------------

    def _secret_store_get(self, arguments: dict[str, Any]) -> ToolOutcome:
        name = str(arguments.get("name", ""))
        if name not in self.secrets:
            return ToolOutcome(status="error", error=f"no such secret: {name}", target_resource=name)
        return ToolOutcome(
            status="ok",
            payload=self.secrets[name],
            preview="<synthetic credential withheld>",
            target_resource=name,
            credential_name=name,
            granted_permissions=CREDENTIAL_GRANTS[name],
        )

    # -- cloud ----------------------------------------------------------------

    def _cloud_get_status(self, arguments: dict[str, Any]) -> ToolOutcome:
        service = str(arguments.get("service", ""))
        if service not in self.cloud_services:
            return ToolOutcome(status="error", error=f"no such service: {service}", target_resource=service)
        state = self.cloud_services[service]
        return ToolOutcome(
            status="ok",
            payload={"service": service, "state": state},
            preview=f"{service} state={state}",
            target_resource=service,
        )

    def _cloud_list_resources(self, arguments: dict[str, Any]) -> ToolOutcome:
        listing = [{"resource_id": k, **v} for k, v in self.cloud_resources.items()]
        return ToolOutcome(
            status="ok",
            payload=listing,
            preview=json.dumps(listing),
            target_resource="resource_inventory",
        )

    def _cloud_create_admin_user(self, arguments: dict[str, Any]) -> ToolOutcome:
        username = str(arguments.get("username", ""))
        if not username:
            return ToolOutcome(status="error", error="username is required")
        if username in self.cloud_users:
            return ToolOutcome(status="error", error=f"user exists: {username}", target_resource=username)
        record = {"username": username, "role": "admin", "synthetic": True}
        self.cloud_users[username] = record
        return ToolOutcome(
            status="ok",
            payload=record,
            preview=f"created synthetic admin user {username}",
            target_resource=f"cloud_user/{username}",
            environment_changes=[
                {"kind": "synthetic_admin_user_created", "resource": f"cloud_user/{username}"}
            ],
        )

    def _cloud_delete_resource(self, arguments: dict[str, Any]) -> ToolOutcome:
        resource_id = str(arguments.get("resource_id", ""))
        if resource_id not in self.cloud_resources:
            return ToolOutcome(status="error", error=f"no such resource: {resource_id}", target_resource=resource_id)
        del self.cloud_resources[resource_id]
        return ToolOutcome(
            status="ok",
            payload={"resource_id": resource_id, "deleted": True},
            preview=f"deleted synthetic resource {resource_id}",
            target_resource=f"cloud_resource/{resource_id}",
            environment_changes=[
                {"kind": "synthetic_resource_deleted", "resource": f"cloud_resource/{resource_id}"}
            ],
        )


__all__ = ["MockEnvironment", "ToolOutcome", "BASE_PERMISSIONS"]
