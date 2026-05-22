"""AI control-plane contracts and v2.2.0 mock assistant skeleton.

This package intentionally exposes only static registry/policy evaluation and
an offline MockAIProvider. It does not connect to real AI providers or execute
capabilities.
"""

from knowledge_app.ai.assistant_models import (
    AssistantCard,
    AssistantMessage,
    AssistantRequest,
    AssistantResponse,
    Citation,
    PolicyNotice,
    SuggestedAction,
)
from knowledge_app.ai.assistant_service import AssistantService
from knowledge_app.ai.capability_registry import CapabilityRegistry, CapabilityRegistryValidationError
from knowledge_app.ai.conversation_models import (
    CitationRecord,
    ConversationRecord,
    ConversationSummary,
    MessageRecord,
    PolicyDecisionRecord,
    TaskReference,
)
from knowledge_app.ai.conversation_persistence_service import (
    ConversationPersistenceService,
    ConversationPersistenceServiceError,
)
from knowledge_app.ai.conversation_store import ConversationStore, ConversationStoreError
from knowledge_app.ai.memory_models import (
    MemoryCandidate,
    MemorySensitivity,
    MemorySource,
    MemoryStatus,
    MemoryType,
    SavedMemory,
)
from knowledge_app.ai.memory_service import MemoryService, MemoryServiceError
from knowledge_app.ai.models import Capability, CapabilityAuditSpec, CapabilityLevel, PermissionDecision
from knowledge_app.ai.mock_provider import MockAIProvider
from knowledge_app.ai.permission_policy import PermissionPolicy
from knowledge_app.ai.persistence_contracts import (
    AIPersistenceContractValidationError,
    validate_backup_inclusion,
    validate_migration_requires_plan_snapshot_approval,
    validate_no_formal_search_injection,
    validate_no_startup_scan_contract,
    validate_privacy_mode_no_write,
    validate_storage_manifest,
    validate_storage_layout,
)
from knowledge_app.ai.persistence_io import AIPersistenceIOError
from knowledge_app.ai.persistence_models import (
    AIBackupInclusion,
    AIClearPlan,
    AIExportPlan,
    AIMigrationPlan,
    AIPersistenceModelValidationError,
    AIPersistencePlan,
    AIRollbackPlan,
    AIStorageLayout,
    AIStorageManifest,
)
from knowledge_app.ai.persistence_service import AIPersistenceServiceError, AIStorageBootstrapService
from knowledge_app.ai.provider import AIProvider
from knowledge_app.ai.retention_models import BackupInclusionPolicy, PrivacyModePolicy, RetentionPolicy

__all__ = [
    "AIProvider",
    "AssistantCard",
    "AssistantMessage",
    "AssistantRequest",
    "AssistantResponse",
    "AssistantService",
    "AIBackupInclusion",
    "AIClearPlan",
    "AIExportPlan",
    "AIMigrationPlan",
    "AIPersistenceContractValidationError",
    "AIPersistenceIOError",
    "AIPersistenceModelValidationError",
    "AIPersistencePlan",
    "AIPersistenceServiceError",
    "AIRollbackPlan",
    "AIStorageBootstrapService",
    "AIStorageLayout",
    "AIStorageManifest",
    "Capability",
    "CapabilityAuditSpec",
    "CapabilityLevel",
    "CapabilityRegistry",
    "CapabilityRegistryValidationError",
    "Citation",
    "CitationRecord",
    "ConversationRecord",
    "ConversationPersistenceService",
    "ConversationPersistenceServiceError",
    "ConversationSummary",
    "ConversationStore",
    "ConversationStoreError",
    "MemoryCandidate",
    "MemoryService",
    "MemoryServiceError",
    "MemorySensitivity",
    "MemorySource",
    "MemoryStatus",
    "MemoryType",
    "MessageRecord",
    "MockAIProvider",
    "PermissionDecision",
    "PermissionPolicy",
    "PolicyDecisionRecord",
    "PolicyNotice",
    "BackupInclusionPolicy",
    "PrivacyModePolicy",
    "RetentionPolicy",
    "SavedMemory",
    "SuggestedAction",
    "TaskReference",
    "validate_backup_inclusion",
    "validate_migration_requires_plan_snapshot_approval",
    "validate_no_formal_search_injection",
    "validate_no_startup_scan_contract",
    "validate_privacy_mode_no_write",
    "validate_storage_manifest",
    "validate_storage_layout",
]
