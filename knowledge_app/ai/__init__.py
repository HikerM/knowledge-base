"""AI control-plane static contracts.

This package intentionally contains only config loading, schema validation,
and permission policy evaluation. It does not connect to AI providers or
execute capabilities.
"""

from knowledge_app.ai.capability_registry import CapabilityRegistry, CapabilityRegistryValidationError
from knowledge_app.ai.models import Capability, CapabilityAuditSpec, CapabilityLevel, PermissionDecision
from knowledge_app.ai.permission_policy import PermissionPolicy

__all__ = [
    "Capability",
    "CapabilityAuditSpec",
    "CapabilityLevel",
    "CapabilityRegistry",
    "CapabilityRegistryValidationError",
    "PermissionDecision",
    "PermissionPolicy",
]
