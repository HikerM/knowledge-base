"""AI capability registry example loader and schema validation."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

import yaml

from knowledge_app.ai.models import Capability, CapabilityLevel


class CapabilityRegistryValidationError(ValueError):
    """Controlled validation error for capability registry examples."""


REQUIRED_CAPABILITY_FIELDS = {
    "id",
    "intent",
    "level",
    "read_only",
    "requires_ai",
    "requires_confirmation",
    "requires_cloud_context_preview",
    "allowed_context",
    "audit",
    "current_version",
}

REQUIRED_AUDIT_FIELDS = {
    "record_intent",
    "record_citations",
    "record_context_ids",
    "record_task_id",
}

FORBIDDEN_SERVICE_MARKERS = (
    "cli",
    "subprocess",
    "shell",
    "powershell",
    "cmd.exe",
    "scripts/kb.py",
    "scripts\\kb.py",
    "os.system",
)


class CapabilityRegistry:
    """In-memory registry loaded from the design-only YAML example."""

    def __init__(self, capabilities: Iterable[Capability] | None = None):
        self._capabilities: Dict[str, Capability] = {}
        self._by_intent: Dict[str, Capability] = {}
        for capability in capabilities or []:
            self._capabilities[capability.id] = capability
            self._by_intent.setdefault(capability.intent, capability)

    @classmethod
    def load_from_yaml(cls, path: Path | str) -> "CapabilityRegistry":
        """Load and validate a capability registry YAML file."""

        path = Path(path)
        try:
            payload = yaml.safe_load(path.read_text(encoding="utf-8"))
        except yaml.YAMLError as exc:
            raise CapabilityRegistryValidationError(f"invalid YAML: {exc}") from exc
        except OSError as exc:
            raise CapabilityRegistryValidationError(f"could not read capability registry: {path}: {exc}") from exc

        if not isinstance(payload, dict):
            raise CapabilityRegistryValidationError("capability registry YAML must be a mapping")
        capabilities_payload = payload.get("capabilities")
        if not isinstance(capabilities_payload, list):
            raise CapabilityRegistryValidationError("capability registry must contain a capabilities list")

        capabilities: List[Capability] = []
        errors: List[str] = []
        seen_ids: set[str] = set()
        for index, item in enumerate(capabilities_payload):
            if not isinstance(item, dict):
                errors.append(f"capabilities[{index}] must be a mapping")
                continue
            try:
                capability = _capability_from_payload(item, index)
                if capability.id in seen_ids:
                    raise CapabilityRegistryValidationError(f"duplicate capability id: {capability.id}")
                seen_ids.add(capability.id)
                capabilities.append(capability)
            except CapabilityRegistryValidationError as exc:
                errors.append(str(exc))

        if errors:
            raise CapabilityRegistryValidationError("; ".join(errors))
        registry = cls(capabilities)
        registry.validate()
        return registry

    def list_capabilities(self) -> List[Capability]:
        return list(self._capabilities.values())

    def get(self, capability_id: str) -> Optional[Capability]:
        return self._capabilities.get(capability_id)

    def get_by_intent(self, intent: str) -> Optional[Capability]:
        return self._by_intent.get(intent)

    def validate(self) -> None:
        errors: List[str] = []
        seen_ids: set[str] = set()
        for capability in self.list_capabilities():
            if capability.id in seen_ids:
                errors.append(f"{capability.id}: duplicate capability id")
                continue
            seen_ids.add(capability.id)
            errors.extend(_validate_capability(capability))
        if errors:
            raise CapabilityRegistryValidationError("; ".join(errors))


def _capability_from_payload(payload: Dict[str, Any], index: int) -> Capability:
    missing = sorted(field for field in REQUIRED_CAPABILITY_FIELDS if field not in payload)
    if missing:
        raise CapabilityRegistryValidationError(f"capabilities[{index}] missing required fields: {', '.join(missing)}")
    if "service" not in payload and "provider" not in payload:
        raise CapabilityRegistryValidationError(f"capabilities[{index}] must declare service or provider")
    if not isinstance(payload["allowed_context"], list):
        raise CapabilityRegistryValidationError(f"capabilities[{index}].allowed_context must be a list")
    if not isinstance(payload["audit"], dict):
        raise CapabilityRegistryValidationError(f"capabilities[{index}].audit must be a mapping")
    missing_audit = sorted(field for field in REQUIRED_AUDIT_FIELDS if field not in payload["audit"])
    if missing_audit:
        raise CapabilityRegistryValidationError(
            f"capabilities[{index}].audit missing required fields: {', '.join(missing_audit)}"
        )
    try:
        return Capability.from_dict(payload)
    except ValueError as exc:
        raise CapabilityRegistryValidationError(f"capabilities[{index}] has invalid field value: {exc}") from exc
    except KeyError as exc:
        raise CapabilityRegistryValidationError(f"capabilities[{index}] missing required field: {exc}") from exc


def _validate_capability(capability: Capability) -> List[str]:
    errors: List[str] = []
    prefix = f"{capability.id}:"

    if capability.level not in set(CapabilityLevel):
        errors.append(f"{prefix} level must be one of L0-L4")

    if not capability.id.strip():
        errors.append(f"{prefix} id must not be empty")
    if not capability.intent.strip():
        errors.append(f"{prefix} intent must not be empty")
    if not capability.current_version.strip():
        errors.append(f"{prefix} current_version must not be empty")

    if capability.level != CapabilityLevel.L4 and not (capability.service or capability.provider):
        errors.append(f"{prefix} non-L4 capability must declare a non-empty service or provider")

    service = capability.service or ""
    service_lower = service.lower()
    if any(marker in service_lower for marker in FORBIDDEN_SERVICE_MARKERS):
        errors.append(f"{prefix} service must not reference CLI, subprocess, shell, or scripts")

    if capability.read_only and capability.level in {CapabilityLevel.L3, CapabilityLevel.L4}:
        errors.append(f"{prefix} read_only=true capabilities cannot be L3 or L4")

    if capability.level == CapabilityLevel.L3:
        if not capability.requires_confirmation:
            errors.append(f"{prefix} L3 must require confirmation")
        missing_execution = [
            key
            for key in ["requires_plan", "requires_snapshot", "requires_approval", "requires_task_queue"]
            if key not in capability.execution_contract
        ]
        if missing_execution:
            errors.append(f"{prefix} L3 execution_contract missing: {', '.join(missing_execution)}")
        for key in ["requires_plan", "requires_snapshot", "requires_approval", "requires_task_queue"]:
            if key in capability.execution_contract and capability.execution_contract.get(key) is not True:
                errors.append(f"{prefix} L3 execution_contract.{key} must be true")

    if capability.level == CapabilityLevel.L4:
        if capability.service or capability.provider:
            errors.append(f"{prefix} L4 capability must not declare an executable service or provider")
        if capability.execution_contract:
            errors.append(f"{prefix} L4 capability must not declare an execution_contract")

    return errors
