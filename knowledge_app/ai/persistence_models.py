"""IO-free static AI persistence contract models.

These models describe future persistent storage boundaries only. They do not
read files, write files, create directories, open SQLite, or call services.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


AI_PERSISTENCE_SCHEMA_VERSION = "0.1"
AI_STORAGE_LAYOUT_VERSION = "ai-storage-layout-v1"
AI_STORAGE_MANIFEST_VERSION = "ai-storage-manifest-v1"

SOURCE_JSONL = "jsonl"
SOURCE_DERIVED = "derived"


class AIPersistenceModelValidationError(ValueError):
    """Raised when a static AI persistence model violates its contract."""


def _default_directories() -> Dict[str, str]:
    return {
        "conversations": "ai/conversations/",
        "memory": "ai/memory/",
        "drafts": "ai/drafts/",
        "indexes": "ai/indexes/",
    }


def _default_source_of_truth() -> Dict[str, str]:
    return {
        "conversations": SOURCE_JSONL,
        "memory": SOURCE_JSONL,
        "drafts": SOURCE_JSONL,
        "indexes": SOURCE_DERIVED,
    }


@dataclass(frozen=True)
class AIStorageManifest:
    """Directory manifest metadata for future workspace-scoped AI storage."""

    schema_version: str
    workspace_id: str
    storage_layout_version: str = AI_STORAGE_LAYOUT_VERSION
    directories: Dict[str, str] = field(default_factory=_default_directories)
    source_of_truth: Dict[str, str] = field(default_factory=_default_source_of_truth)
    privacy_mode_default: bool = False
    schema_min_reader_version: str = "2.5.1-static-contract"
    schema_writer_version: Optional[str] = None
    indexes_derived_only: bool = True
    indexes_rebuildable: bool = True

    def validate(self) -> "AIStorageManifest":
        _require_text(self.schema_version, "schema_version")
        _require_text(self.workspace_id, "workspace_id")
        _require_text(self.storage_layout_version, "storage_layout_version")
        _require_dict(self.directories, "directories")
        _require_dict(self.source_of_truth, "source_of_truth")
        _require_bool(self.privacy_mode_default, "privacy_mode_default")
        _require_text(self.schema_min_reader_version, "schema_min_reader_version")
        _require_bool(self.indexes_derived_only, "indexes_derived_only")
        _require_bool(self.indexes_rebuildable, "indexes_rebuildable")
        _require_keys(
            self.directories,
            ["conversations", "memory", "drafts", "indexes"],
            "directories",
        )
        _require_keys(
            self.source_of_truth,
            ["conversations", "memory", "drafts", "indexes"],
            "source_of_truth",
        )
        if self.source_of_truth["indexes"] != SOURCE_DERIVED:
            raise AIPersistenceModelValidationError("indexes must be marked as derived source")
        if self.indexes_derived_only is not True:
            raise AIPersistenceModelValidationError("indexes must be derived only")
        if self.indexes_rebuildable is not True:
            raise AIPersistenceModelValidationError("derived indexes must be rebuildable")
        return self

    def to_dict(self) -> Dict[str, Any]:
        self.validate()
        return {
            "schema_version": self.schema_version,
            "workspace_id": self.workspace_id,
            "storage_layout_version": self.storage_layout_version,
            "directories": dict(self.directories),
            "source_of_truth": dict(self.source_of_truth),
            "privacy_mode_default": self.privacy_mode_default,
            "schema_min_reader_version": self.schema_min_reader_version,
            "schema_writer_version": self.schema_writer_version,
            "indexes_derived_only": self.indexes_derived_only,
            "indexes_rebuildable": self.indexes_rebuildable,
        }

    @classmethod
    def from_dict(cls, payload: Dict[str, Any]) -> "AIStorageManifest":
        _require_dict(payload, "AIStorageManifest")
        _require_keys(payload, ["schema_version", "workspace_id"], "AIStorageManifest")
        return cls(
            schema_version=str(payload["schema_version"]),
            workspace_id=str(payload["workspace_id"]),
            storage_layout_version=str(payload.get("storage_layout_version") or AI_STORAGE_LAYOUT_VERSION),
            directories=_optional_dict(payload, "directories", _default_directories()),
            source_of_truth=_optional_dict(payload, "source_of_truth", _default_source_of_truth()),
            privacy_mode_default=_optional_bool(payload, "privacy_mode_default", False),
            schema_min_reader_version=str(payload.get("schema_min_reader_version") or "2.5.1-static-contract"),
            schema_writer_version=_optional_string(payload.get("schema_writer_version")),
            indexes_derived_only=_optional_bool(payload, "indexes_derived_only", True),
            indexes_rebuildable=_optional_bool(payload, "indexes_rebuildable", True),
        ).validate()


@dataclass(frozen=True)
class AIStorageLayout:
    """Static path contract for future AI persistence storage."""

    schema_version: str
    workspace_id: str
    workspace_root: str
    storage_root: str
    conversations_path: str
    memory_path: str
    drafts_path: str
    indexes_path: str
    manifest: AIStorageManifest
    install_root: Optional[str] = None
    source_records_are_truth: bool = True
    indexes_derived_only: bool = True
    indexes_rebuildable: bool = True
    storage_growth_limit_mb: int = 1024

    def validate(self) -> "AIStorageLayout":
        _require_text(self.schema_version, "schema_version")
        _require_text(self.workspace_id, "workspace_id")
        _require_text(self.workspace_root, "workspace_root")
        _require_text(self.storage_root, "storage_root")
        _require_text(self.conversations_path, "conversations_path")
        _require_text(self.memory_path, "memory_path")
        _require_text(self.drafts_path, "drafts_path")
        _require_text(self.indexes_path, "indexes_path")
        _require_bool(self.source_records_are_truth, "source_records_are_truth")
        _require_bool(self.indexes_derived_only, "indexes_derived_only")
        _require_bool(self.indexes_rebuildable, "indexes_rebuildable")
        _require_positive_int(self.storage_growth_limit_mb, "storage_growth_limit_mb")
        if not isinstance(self.manifest, AIStorageManifest):
            raise AIPersistenceModelValidationError("manifest must be an AIStorageManifest")
        self.manifest.validate()
        if self.source_records_are_truth is not True:
            raise AIPersistenceModelValidationError("AI source records must be the source of truth")
        if self.indexes_derived_only is not True:
            raise AIPersistenceModelValidationError("indexes must be derived only")
        if self.indexes_rebuildable is not True:
            raise AIPersistenceModelValidationError("derived indexes must be rebuildable")
        _validate_storage_path_boundary(self)
        return self

    def to_dict(self) -> Dict[str, Any]:
        self.validate()
        return {
            "schema_version": self.schema_version,
            "workspace_id": self.workspace_id,
            "workspace_root": self.workspace_root,
            "storage_root": self.storage_root,
            "conversations_path": self.conversations_path,
            "memory_path": self.memory_path,
            "drafts_path": self.drafts_path,
            "indexes_path": self.indexes_path,
            "manifest": self.manifest.to_dict(),
            "install_root": self.install_root,
            "source_records_are_truth": self.source_records_are_truth,
            "indexes_derived_only": self.indexes_derived_only,
            "indexes_rebuildable": self.indexes_rebuildable,
            "storage_growth_limit_mb": self.storage_growth_limit_mb,
        }

    @classmethod
    def from_dict(cls, payload: Dict[str, Any]) -> "AIStorageLayout":
        _require_dict(payload, "AIStorageLayout")
        _require_keys(
            payload,
            [
                "schema_version",
                "workspace_id",
                "workspace_root",
                "storage_root",
                "conversations_path",
                "memory_path",
                "drafts_path",
                "indexes_path",
                "manifest",
            ],
            "AIStorageLayout",
        )
        return cls(
            schema_version=str(payload["schema_version"]),
            workspace_id=str(payload["workspace_id"]),
            workspace_root=str(payload["workspace_root"]),
            storage_root=str(payload["storage_root"]),
            conversations_path=str(payload["conversations_path"]),
            memory_path=str(payload["memory_path"]),
            drafts_path=str(payload["drafts_path"]),
            indexes_path=str(payload["indexes_path"]),
            manifest=AIStorageManifest.from_dict(payload["manifest"]),
            install_root=_optional_string(payload.get("install_root")),
            source_records_are_truth=_optional_bool(payload, "source_records_are_truth", True),
            indexes_derived_only=_optional_bool(payload, "indexes_derived_only", True),
            indexes_rebuildable=_optional_bool(payload, "indexes_rebuildable", True),
            storage_growth_limit_mb=_optional_positive_int(payload, "storage_growth_limit_mb", 1024),
        ).validate()


@dataclass(frozen=True)
class AIPersistencePlan:
    """Static startup, listing, privacy, and formal-search boundary contract."""

    schema_version: str
    plan_id: str
    workspace_id: str
    layout: AIStorageLayout
    scan_all: bool = False
    startup_scan_conversations: bool = False
    startup_scan_memory: bool = False
    startup_scan_drafts: bool = False
    inject_into_formal_search: bool = False
    list_conversations_paginated: bool = True
    list_memories_paginated: bool = True
    conversation_page_size: int = 50
    memory_page_size: int = 50
    derived_index_rebuildable: bool = True
    storage_growth_limit_mb: int = 1024
    privacy_mode: bool = False
    would_write_persistent_data: bool = False

    def validate(self) -> "AIPersistencePlan":
        _require_text(self.schema_version, "schema_version")
        _require_text(self.plan_id, "plan_id")
        _require_text(self.workspace_id, "workspace_id")
        if not isinstance(self.layout, AIStorageLayout):
            raise AIPersistenceModelValidationError("layout must be an AIStorageLayout")
        self.layout.validate()
        for field_name in [
            "scan_all",
            "startup_scan_conversations",
            "startup_scan_memory",
            "startup_scan_drafts",
            "inject_into_formal_search",
            "list_conversations_paginated",
            "list_memories_paginated",
            "derived_index_rebuildable",
            "privacy_mode",
            "would_write_persistent_data",
        ]:
            _require_bool(getattr(self, field_name), field_name)
        _require_positive_int(self.conversation_page_size, "conversation_page_size")
        _require_positive_int(self.memory_page_size, "memory_page_size")
        _require_positive_int(self.storage_growth_limit_mb, "storage_growth_limit_mb")
        if self.derived_index_rebuildable is not True:
            raise AIPersistenceModelValidationError("derived index must be rebuildable")
        return self

    def to_dict(self) -> Dict[str, Any]:
        self.validate()
        return {
            "schema_version": self.schema_version,
            "plan_id": self.plan_id,
            "workspace_id": self.workspace_id,
            "layout": self.layout.to_dict(),
            "scan_all": self.scan_all,
            "startup_scan_conversations": self.startup_scan_conversations,
            "startup_scan_memory": self.startup_scan_memory,
            "startup_scan_drafts": self.startup_scan_drafts,
            "inject_into_formal_search": self.inject_into_formal_search,
            "list_conversations_paginated": self.list_conversations_paginated,
            "list_memories_paginated": self.list_memories_paginated,
            "conversation_page_size": self.conversation_page_size,
            "memory_page_size": self.memory_page_size,
            "derived_index_rebuildable": self.derived_index_rebuildable,
            "storage_growth_limit_mb": self.storage_growth_limit_mb,
            "privacy_mode": self.privacy_mode,
            "would_write_persistent_data": self.would_write_persistent_data,
        }

    @classmethod
    def from_dict(cls, payload: Dict[str, Any]) -> "AIPersistencePlan":
        _require_dict(payload, "AIPersistencePlan")
        _require_keys(payload, ["schema_version", "plan_id", "workspace_id", "layout"], "AIPersistencePlan")
        return cls(
            schema_version=str(payload["schema_version"]),
            plan_id=str(payload["plan_id"]),
            workspace_id=str(payload["workspace_id"]),
            layout=AIStorageLayout.from_dict(payload["layout"]),
            scan_all=_optional_bool(payload, "scan_all", False),
            startup_scan_conversations=_optional_bool(payload, "startup_scan_conversations", False),
            startup_scan_memory=_optional_bool(payload, "startup_scan_memory", False),
            startup_scan_drafts=_optional_bool(payload, "startup_scan_drafts", False),
            inject_into_formal_search=_optional_bool(payload, "inject_into_formal_search", False),
            list_conversations_paginated=_optional_bool(payload, "list_conversations_paginated", True),
            list_memories_paginated=_optional_bool(payload, "list_memories_paginated", True),
            conversation_page_size=_optional_positive_int(payload, "conversation_page_size", 50),
            memory_page_size=_optional_positive_int(payload, "memory_page_size", 50),
            derived_index_rebuildable=_optional_bool(payload, "derived_index_rebuildable", True),
            storage_growth_limit_mb=_optional_positive_int(payload, "storage_growth_limit_mb", 1024),
            privacy_mode=_optional_bool(payload, "privacy_mode", False),
            would_write_persistent_data=_optional_bool(payload, "would_write_persistent_data", False),
        ).validate()


@dataclass(frozen=True)
class AIRollbackPlan:
    """Static rollback contract for future AI persistence migrations."""

    schema_version: str
    rollback_id: str
    workspace_id: str
    ai_storage_only: bool = True
    restore_paths: List[str] = field(default_factory=list)
    remove_paths: List[str] = field(default_factory=list)
    conflicts: List[str] = field(default_factory=list)
    privacy_impact: str = "ai persistence rollback only"
    backup_contains_ai_conversations: bool = False
    backup_contains_ai_memory: bool = False
    backup_contains_ai_drafts: bool = False
    touches_knowledge: bool = False
    touches_kb_index: bool = False
    marks_derived_indexes_stale: bool = True
    requires_approval: bool = True
    validation_commands: List[str] = field(default_factory=list)

    def validate(self) -> "AIRollbackPlan":
        _require_text(self.schema_version, "schema_version")
        _require_text(self.rollback_id, "rollback_id")
        _require_text(self.workspace_id, "workspace_id")
        _require_bool(self.ai_storage_only, "ai_storage_only")
        _require_list(self.restore_paths, "restore_paths")
        _require_list(self.remove_paths, "remove_paths")
        _require_list(self.conflicts, "conflicts")
        _require_text(self.privacy_impact, "privacy_impact")
        for field_name in [
            "backup_contains_ai_conversations",
            "backup_contains_ai_memory",
            "backup_contains_ai_drafts",
            "touches_knowledge",
            "touches_kb_index",
            "marks_derived_indexes_stale",
            "requires_approval",
        ]:
            _require_bool(getattr(self, field_name), field_name)
        _require_list(self.validation_commands, "validation_commands")
        if self.ai_storage_only is not True:
            raise AIPersistenceModelValidationError("rollback must be limited to AI persistence storage")
        if self.touches_knowledge:
            raise AIPersistenceModelValidationError("rollback must not touch Markdown knowledge")
        if self.touches_kb_index:
            raise AIPersistenceModelValidationError("rollback must not touch .kb/index.sqlite")
        if self.marks_derived_indexes_stale is not True:
            raise AIPersistenceModelValidationError("rollback must mark AI derived indexes stale")
        if self.requires_approval is not True:
            raise AIPersistenceModelValidationError("rollback must require explicit approval")
        _require_text_list(self.restore_paths, "restore_paths")
        _require_text_list(self.remove_paths, "remove_paths")
        _require_text_list(self.conflicts, "conflicts")
        _require_text_list(self.validation_commands, "validation_commands")
        return self

    def to_dict(self) -> Dict[str, Any]:
        self.validate()
        return {
            "schema_version": self.schema_version,
            "rollback_id": self.rollback_id,
            "workspace_id": self.workspace_id,
            "ai_storage_only": self.ai_storage_only,
            "restore_paths": list(self.restore_paths),
            "remove_paths": list(self.remove_paths),
            "conflicts": list(self.conflicts),
            "privacy_impact": self.privacy_impact,
            "backup_contains_ai_conversations": self.backup_contains_ai_conversations,
            "backup_contains_ai_memory": self.backup_contains_ai_memory,
            "backup_contains_ai_drafts": self.backup_contains_ai_drafts,
            "touches_knowledge": self.touches_knowledge,
            "touches_kb_index": self.touches_kb_index,
            "marks_derived_indexes_stale": self.marks_derived_indexes_stale,
            "requires_approval": self.requires_approval,
            "validation_commands": list(self.validation_commands),
        }

    @classmethod
    def from_dict(cls, payload: Dict[str, Any]) -> "AIRollbackPlan":
        _require_dict(payload, "AIRollbackPlan")
        _require_keys(payload, ["schema_version", "rollback_id", "workspace_id"], "AIRollbackPlan")
        return cls(
            schema_version=str(payload["schema_version"]),
            rollback_id=str(payload["rollback_id"]),
            workspace_id=str(payload["workspace_id"]),
            ai_storage_only=_optional_bool(payload, "ai_storage_only", True),
            restore_paths=[str(item) for item in _optional_list(payload, "restore_paths", [])],
            remove_paths=[str(item) for item in _optional_list(payload, "remove_paths", [])],
            conflicts=[str(item) for item in _optional_list(payload, "conflicts", [])],
            privacy_impact=str(payload.get("privacy_impact") or "ai persistence rollback only"),
            backup_contains_ai_conversations=_optional_bool(payload, "backup_contains_ai_conversations", False),
            backup_contains_ai_memory=_optional_bool(payload, "backup_contains_ai_memory", False),
            backup_contains_ai_drafts=_optional_bool(payload, "backup_contains_ai_drafts", False),
            touches_knowledge=_optional_bool(payload, "touches_knowledge", False),
            touches_kb_index=_optional_bool(payload, "touches_kb_index", False),
            marks_derived_indexes_stale=_optional_bool(payload, "marks_derived_indexes_stale", True),
            requires_approval=_optional_bool(payload, "requires_approval", True),
            validation_commands=[str(item) for item in _optional_list(payload, "validation_commands", [])],
        ).validate()


@dataclass(frozen=True)
class AIMigrationPlan:
    """Static migration contract for future AI persistence schema changes."""

    schema_version: str
    migration_id: str
    workspace_id: str
    source_schema_versions: Dict[str, str]
    target_schema_versions: Dict[str, str]
    rollback_plan: AIRollbackPlan
    dry_run: bool = True
    would_modify: bool = False
    blocked: bool = False
    blockers: List[str] = field(default_factory=list)
    actions: List[str] = field(default_factory=list)
    impacted_paths: List[str] = field(default_factory=list)
    estimated_record_counts: Dict[str, int] = field(default_factory=dict)
    requires_snapshot: bool = True
    requires_approval: bool = True
    plan_first: bool = True
    silent_migration: bool = False
    rebuild_derived_index: bool = False
    validation_commands: List[str] = field(default_factory=list)
    privacy_warnings: List[str] = field(default_factory=list)

    def validate(self) -> "AIMigrationPlan":
        _require_text(self.schema_version, "schema_version")
        _require_text(self.migration_id, "migration_id")
        _require_text(self.workspace_id, "workspace_id")
        _require_dict(self.source_schema_versions, "source_schema_versions")
        _require_dict(self.target_schema_versions, "target_schema_versions")
        if not isinstance(self.rollback_plan, AIRollbackPlan):
            raise AIPersistenceModelValidationError("rollback_plan must be an AIRollbackPlan")
        self.rollback_plan.validate()
        for field_name in [
            "dry_run",
            "would_modify",
            "blocked",
            "requires_snapshot",
            "requires_approval",
            "plan_first",
            "silent_migration",
            "rebuild_derived_index",
        ]:
            _require_bool(getattr(self, field_name), field_name)
        _require_list(self.blockers, "blockers")
        _require_list(self.actions, "actions")
        _require_list(self.impacted_paths, "impacted_paths")
        _require_dict(self.estimated_record_counts, "estimated_record_counts")
        _require_list(self.validation_commands, "validation_commands")
        _require_list(self.privacy_warnings, "privacy_warnings")
        _require_text_dict(self.source_schema_versions, "source_schema_versions")
        _require_text_dict(self.target_schema_versions, "target_schema_versions")
        _require_text_list(self.blockers, "blockers")
        _require_text_list(self.actions, "actions")
        _require_text_list(self.impacted_paths, "impacted_paths")
        _require_text_list(self.validation_commands, "validation_commands")
        _require_text_list(self.privacy_warnings, "privacy_warnings")
        for key, value in self.estimated_record_counts.items():
            _require_text(key, "estimated_record_counts key")
            _require_non_negative_int(value, f"estimated_record_counts.{key}")
        if self.dry_run is not True:
            raise AIPersistenceModelValidationError("migration plan must be plan-first dry_run=true")
        if self.would_modify is not False:
            raise AIPersistenceModelValidationError("static migration plan must set would_modify=false")
        if self.requires_snapshot is not True:
            raise AIPersistenceModelValidationError("migration plan must require local snapshot")
        if self.requires_approval is not True:
            raise AIPersistenceModelValidationError("migration plan must require approval")
        if self.plan_first is not True:
            raise AIPersistenceModelValidationError("migration must be plan-first")
        if self.silent_migration:
            raise AIPersistenceModelValidationError("silent migration is forbidden")
        return self

    def to_dict(self) -> Dict[str, Any]:
        self.validate()
        return {
            "schema_version": self.schema_version,
            "migration_id": self.migration_id,
            "workspace_id": self.workspace_id,
            "source_schema_versions": dict(self.source_schema_versions),
            "target_schema_versions": dict(self.target_schema_versions),
            "rollback_plan": self.rollback_plan.to_dict(),
            "dry_run": self.dry_run,
            "would_modify": self.would_modify,
            "blocked": self.blocked,
            "blockers": list(self.blockers),
            "actions": list(self.actions),
            "impacted_paths": list(self.impacted_paths),
            "estimated_record_counts": dict(self.estimated_record_counts),
            "requires_snapshot": self.requires_snapshot,
            "requires_approval": self.requires_approval,
            "plan_first": self.plan_first,
            "silent_migration": self.silent_migration,
            "rebuild_derived_index": self.rebuild_derived_index,
            "validation_commands": list(self.validation_commands),
            "privacy_warnings": list(self.privacy_warnings),
        }

    @classmethod
    def from_dict(cls, payload: Dict[str, Any]) -> "AIMigrationPlan":
        _require_dict(payload, "AIMigrationPlan")
        _require_keys(
            payload,
            [
                "schema_version",
                "migration_id",
                "workspace_id",
                "source_schema_versions",
                "target_schema_versions",
                "rollback_plan",
            ],
            "AIMigrationPlan",
        )
        return cls(
            schema_version=str(payload["schema_version"]),
            migration_id=str(payload["migration_id"]),
            workspace_id=str(payload["workspace_id"]),
            source_schema_versions={str(k): str(v) for k, v in _require_dict(payload["source_schema_versions"], "source_schema_versions").items()},
            target_schema_versions={str(k): str(v) for k, v in _require_dict(payload["target_schema_versions"], "target_schema_versions").items()},
            rollback_plan=AIRollbackPlan.from_dict(payload["rollback_plan"]),
            dry_run=_optional_bool(payload, "dry_run", True),
            would_modify=_optional_bool(payload, "would_modify", False),
            blocked=_optional_bool(payload, "blocked", False),
            blockers=[str(item) for item in _optional_list(payload, "blockers", [])],
            actions=[str(item) for item in _optional_list(payload, "actions", [])],
            impacted_paths=[str(item) for item in _optional_list(payload, "impacted_paths", [])],
            estimated_record_counts={
                str(k): _require_non_negative_int(v, f"estimated_record_counts.{k}")
                for k, v in _optional_dict(payload, "estimated_record_counts", {}).items()
            },
            requires_snapshot=_optional_bool(payload, "requires_snapshot", True),
            requires_approval=_optional_bool(payload, "requires_approval", True),
            plan_first=_optional_bool(payload, "plan_first", True),
            silent_migration=_optional_bool(payload, "silent_migration", False),
            rebuild_derived_index=_optional_bool(payload, "rebuild_derived_index", False),
            validation_commands=[str(item) for item in _optional_list(payload, "validation_commands", [])],
            privacy_warnings=[str(item) for item in _optional_list(payload, "privacy_warnings", [])],
        ).validate()


@dataclass(frozen=True)
class AIBackupInclusion:
    """Static privacy-first backup inclusion flags for future AI data."""

    schema_version: str = AI_PERSISTENCE_SCHEMA_VERSION
    include_ai_conversations: bool = False
    include_ai_memory: bool = False
    include_ai_drafts: bool = False
    include_ai_indexes: bool = False
    ai_data_privacy_warning_acknowledged: bool = False
    ai_data_included_paths: List[str] = field(default_factory=list)
    ai_data_excluded_paths: List[str] = field(
        default_factory=lambda: [
            "ai/conversations/",
            "ai/memory/",
            "ai/drafts/",
            "ai/indexes/",
        ]
    )

    def validate(self) -> "AIBackupInclusion":
        _require_text(self.schema_version, "schema_version")
        for field_name in [
            "include_ai_conversations",
            "include_ai_memory",
            "include_ai_drafts",
            "include_ai_indexes",
            "ai_data_privacy_warning_acknowledged",
        ]:
            _require_bool(getattr(self, field_name), field_name)
        _require_list(self.ai_data_included_paths, "ai_data_included_paths")
        _require_list(self.ai_data_excluded_paths, "ai_data_excluded_paths")
        _require_text_list(self.ai_data_included_paths, "ai_data_included_paths")
        _require_text_list(self.ai_data_excluded_paths, "ai_data_excluded_paths")
        return self

    def to_dict(self) -> Dict[str, Any]:
        self.validate()
        return {
            "schema_version": self.schema_version,
            "include_ai_conversations": self.include_ai_conversations,
            "include_ai_memory": self.include_ai_memory,
            "include_ai_drafts": self.include_ai_drafts,
            "include_ai_indexes": self.include_ai_indexes,
            "ai_data_privacy_warning_acknowledged": self.ai_data_privacy_warning_acknowledged,
            "ai_data_included_paths": list(self.ai_data_included_paths),
            "ai_data_excluded_paths": list(self.ai_data_excluded_paths),
        }

    @classmethod
    def from_dict(cls, payload: Dict[str, Any]) -> "AIBackupInclusion":
        _require_dict(payload, "AIBackupInclusion")
        return cls(
            schema_version=str(payload.get("schema_version") or AI_PERSISTENCE_SCHEMA_VERSION),
            include_ai_conversations=_optional_bool(payload, "include_ai_conversations", False),
            include_ai_memory=_optional_bool(payload, "include_ai_memory", False),
            include_ai_drafts=_optional_bool(payload, "include_ai_drafts", False),
            include_ai_indexes=_optional_bool(payload, "include_ai_indexes", False),
            ai_data_privacy_warning_acknowledged=_optional_bool(
                payload, "ai_data_privacy_warning_acknowledged", False
            ),
            ai_data_included_paths=[str(item) for item in _optional_list(payload, "ai_data_included_paths", [])],
            ai_data_excluded_paths=[
                str(item)
                for item in _optional_list(
                    payload,
                    "ai_data_excluded_paths",
                    ["ai/conversations/", "ai/memory/", "ai/drafts/", "ai/indexes/"],
                )
            ],
        ).validate()


@dataclass(frozen=True)
class AIExportPlan:
    """Static export plan for future AI conversation and memory exports."""

    schema_version: str
    export_id: str
    workspace_id: str
    export_scope: str
    source_ids: List[str] = field(default_factory=list)
    formats: List[str] = field(default_factory=lambda: ["json"])
    redact_sensitive: bool = True
    redact_secrets: bool = True
    include_context_preview_bodies: bool = False
    include_derived_indexes: bool = False
    include_task_logs: bool = False
    not_formal_knowledge: bool = True

    def validate(self) -> "AIExportPlan":
        _require_text(self.schema_version, "schema_version")
        _require_text(self.export_id, "export_id")
        _require_text(self.workspace_id, "workspace_id")
        _require_choice(
            self.export_scope,
            {
                "one_conversation",
                "selected_conversations",
                "all_conversations",
                "saved_memory",
                "disabled_memory",
                "selected_memory",
                "candidates",
            },
            "export_scope",
        )
        _require_list(self.source_ids, "source_ids")
        _require_list(self.formats, "formats")
        _require_text_list(self.source_ids, "source_ids")
        _require_text_list(self.formats, "formats")
        for field_name in [
            "redact_sensitive",
            "redact_secrets",
            "include_context_preview_bodies",
            "include_derived_indexes",
            "include_task_logs",
            "not_formal_knowledge",
        ]:
            _require_bool(getattr(self, field_name), field_name)
        if self.redact_sensitive is not True:
            raise AIPersistenceModelValidationError("export must redact sensitive data by default")
        if self.redact_secrets is not True:
            raise AIPersistenceModelValidationError("export must redact secrets by default")
        if self.not_formal_knowledge is not True:
            raise AIPersistenceModelValidationError("exported AI data must remain non-formal")
        return self

    def to_dict(self) -> Dict[str, Any]:
        self.validate()
        return {
            "schema_version": self.schema_version,
            "export_id": self.export_id,
            "workspace_id": self.workspace_id,
            "export_scope": self.export_scope,
            "source_ids": list(self.source_ids),
            "formats": list(self.formats),
            "redact_sensitive": self.redact_sensitive,
            "redact_secrets": self.redact_secrets,
            "include_context_preview_bodies": self.include_context_preview_bodies,
            "include_derived_indexes": self.include_derived_indexes,
            "include_task_logs": self.include_task_logs,
            "not_formal_knowledge": self.not_formal_knowledge,
        }

    @classmethod
    def from_dict(cls, payload: Dict[str, Any]) -> "AIExportPlan":
        _require_dict(payload, "AIExportPlan")
        _require_keys(payload, ["schema_version", "export_id", "workspace_id", "export_scope"], "AIExportPlan")
        return cls(
            schema_version=str(payload["schema_version"]),
            export_id=str(payload["export_id"]),
            workspace_id=str(payload["workspace_id"]),
            export_scope=str(payload["export_scope"]),
            source_ids=[str(item) for item in _optional_list(payload, "source_ids", [])],
            formats=[str(item) for item in _optional_list(payload, "formats", ["json"])],
            redact_sensitive=_optional_bool(payload, "redact_sensitive", True),
            redact_secrets=_optional_bool(payload, "redact_secrets", True),
            include_context_preview_bodies=_optional_bool(payload, "include_context_preview_bodies", False),
            include_derived_indexes=_optional_bool(payload, "include_derived_indexes", False),
            include_task_logs=_optional_bool(payload, "include_task_logs", False),
            not_formal_knowledge=_optional_bool(payload, "not_formal_knowledge", True),
        ).validate()


@dataclass(frozen=True)
class AIClearPlan:
    """Static clear/delete plan for future AI data controls."""

    schema_version: str
    clear_id: str
    workspace_id: str
    clear_conversations: bool = False
    clear_memory: bool = False
    clear_drafts: bool = False
    clear_candidates: bool = False
    clear_suppressions: bool = False
    clear_derived_indexes: bool = False
    delete_workspace: bool = False
    delete_knowledge: bool = False
    clear_markdown_knowledge: bool = False
    current_workspace_only: bool = True
    requires_approval: bool = True
    marks_derived_indexes_stale: bool = True

    def validate(self) -> "AIClearPlan":
        _require_text(self.schema_version, "schema_version")
        _require_text(self.clear_id, "clear_id")
        _require_text(self.workspace_id, "workspace_id")
        for field_name in [
            "clear_conversations",
            "clear_memory",
            "clear_drafts",
            "clear_candidates",
            "clear_suppressions",
            "clear_derived_indexes",
            "delete_workspace",
            "delete_knowledge",
            "clear_markdown_knowledge",
            "current_workspace_only",
            "requires_approval",
            "marks_derived_indexes_stale",
        ]:
            _require_bool(getattr(self, field_name), field_name)
        if self.delete_knowledge or self.clear_markdown_knowledge:
            raise AIPersistenceModelValidationError("AI clear plan must not delete Markdown knowledge")
        if self.delete_workspace:
            raise AIPersistenceModelValidationError("AI clear plan must not delete workspace")
        if self.current_workspace_only is not True:
            raise AIPersistenceModelValidationError("AI clear plan must be scoped to current workspace")
        if self.requires_approval is not True:
            raise AIPersistenceModelValidationError("AI clear plan must require approval")
        if self.marks_derived_indexes_stale is not True:
            raise AIPersistenceModelValidationError("AI clear plan must mark derived indexes stale")
        return self

    def to_dict(self) -> Dict[str, Any]:
        self.validate()
        return {
            "schema_version": self.schema_version,
            "clear_id": self.clear_id,
            "workspace_id": self.workspace_id,
            "clear_conversations": self.clear_conversations,
            "clear_memory": self.clear_memory,
            "clear_drafts": self.clear_drafts,
            "clear_candidates": self.clear_candidates,
            "clear_suppressions": self.clear_suppressions,
            "clear_derived_indexes": self.clear_derived_indexes,
            "delete_workspace": self.delete_workspace,
            "delete_knowledge": self.delete_knowledge,
            "clear_markdown_knowledge": self.clear_markdown_knowledge,
            "current_workspace_only": self.current_workspace_only,
            "requires_approval": self.requires_approval,
            "marks_derived_indexes_stale": self.marks_derived_indexes_stale,
        }

    @classmethod
    def from_dict(cls, payload: Dict[str, Any]) -> "AIClearPlan":
        _require_dict(payload, "AIClearPlan")
        _require_keys(payload, ["schema_version", "clear_id", "workspace_id"], "AIClearPlan")
        return cls(
            schema_version=str(payload["schema_version"]),
            clear_id=str(payload["clear_id"]),
            workspace_id=str(payload["workspace_id"]),
            clear_conversations=_optional_bool(payload, "clear_conversations", False),
            clear_memory=_optional_bool(payload, "clear_memory", False),
            clear_drafts=_optional_bool(payload, "clear_drafts", False),
            clear_candidates=_optional_bool(payload, "clear_candidates", False),
            clear_suppressions=_optional_bool(payload, "clear_suppressions", False),
            clear_derived_indexes=_optional_bool(payload, "clear_derived_indexes", False),
            delete_workspace=_optional_bool(payload, "delete_workspace", False),
            delete_knowledge=_optional_bool(payload, "delete_knowledge", False),
            clear_markdown_knowledge=_optional_bool(payload, "clear_markdown_knowledge", False),
            current_workspace_only=_optional_bool(payload, "current_workspace_only", True),
            requires_approval=_optional_bool(payload, "requires_approval", True),
            marks_derived_indexes_stale=_optional_bool(payload, "marks_derived_indexes_stale", True),
        ).validate()


def _validate_storage_path_boundary(layout: AIStorageLayout) -> None:
    workspace_root = _normalize_path(layout.workspace_root)
    storage_root = _normalize_path(layout.storage_root)
    conversations_path = _normalize_path(layout.conversations_path)
    memory_path = _normalize_path(layout.memory_path)
    drafts_path = _normalize_path(layout.drafts_path)
    indexes_path = _normalize_path(layout.indexes_path)
    install_root = _normalize_path(layout.install_root) if layout.install_root else None

    if not _is_under_or_equal(storage_root, workspace_root):
        raise AIPersistenceModelValidationError("storage_root must be workspace scoped")
    if not _path_basename(storage_root) == "ai":
        raise AIPersistenceModelValidationError("storage_root must be the workspace-scoped ai directory")
    if install_root and _is_under_or_equal(storage_root, install_root):
        raise AIPersistenceModelValidationError("storage_root must not be inside install dir")

    for field_name, path in [
        ("storage_root", storage_root),
        ("conversations_path", conversations_path),
        ("memory_path", memory_path),
        ("drafts_path", drafts_path),
        ("indexes_path", indexes_path),
    ]:
        _reject_forbidden_ai_path(path, field_name, workspace_root, install_root)

    for field_name, path in [
        ("conversations_path", conversations_path),
        ("memory_path", memory_path),
        ("drafts_path", drafts_path),
        ("indexes_path", indexes_path),
    ]:
        if not _is_under_or_equal(path, storage_root):
            raise AIPersistenceModelValidationError(f"{field_name} must be under storage_root")


def _reject_forbidden_ai_path(path: str, field_name: str, workspace_root: str, install_root: Optional[str]) -> None:
    if _contains_path_segment(path, "knowledge") and _is_under_or_equal(path, workspace_root):
        raise AIPersistenceModelValidationError(f"{field_name} must not be inside knowledge/")
    if _contains_path_segment(path, ".kb") and _is_under_or_equal(path, workspace_root):
        raise AIPersistenceModelValidationError(f"{field_name} must not be inside .kb/")
    if install_root and _is_under_or_equal(path, install_root):
        raise AIPersistenceModelValidationError(f"{field_name} must not be inside install dir")
    if "/program files/" in f"/{path}/":
        raise AIPersistenceModelValidationError(f"{field_name} must not be inside install dir")


def _normalize_path(value: Optional[str]) -> str:
    text = str(value or "").strip().replace("\\", "/")
    while "//" in text:
        text = text.replace("//", "/")
    if len(text) > 1:
        text = text.rstrip("/")
    return text.lower()


def _path_basename(path: str) -> str:
    return path.rsplit("/", 1)[-1]


def _is_under_or_equal(child: str, parent: str) -> bool:
    if not parent:
        return False
    return child == parent or child.startswith(parent.rstrip("/") + "/")


def _contains_path_segment(path: str, segment: str) -> bool:
    parts = [part for part in path.split("/") if part]
    return segment.lower() in parts


def _require_keys(payload: Dict[str, Any], keys: List[str], model_name: str) -> None:
    _require_dict(payload, model_name)
    missing = [key for key in keys if key not in payload]
    if missing:
        raise AIPersistenceModelValidationError(f"{model_name} missing required fields: {', '.join(missing)}")


def _require_text(value: Any, field_name: str) -> None:
    if value is None or not isinstance(value, str) or not value.strip():
        raise AIPersistenceModelValidationError(f"{field_name} is required")


def _require_choice(value: Any, allowed: set[str], field_name: str) -> None:
    if not isinstance(value, str):
        raise AIPersistenceModelValidationError(f"{field_name} must be a string enum value")
    if value not in allowed:
        allowed_text = ", ".join(sorted(allowed))
        raise AIPersistenceModelValidationError(f"{field_name} must be one of: {allowed_text}")


def _require_bool(value: Any, field_name: str) -> bool:
    if type(value) is not bool:
        raise AIPersistenceModelValidationError(f"{field_name} must be a boolean")
    return value


def _optional_bool(payload: Dict[str, Any], field_name: str, default: bool) -> bool:
    if field_name not in payload:
        return default
    return _require_bool(payload[field_name], field_name)


def _require_positive_int(value: Any, field_name: str) -> int:
    if type(value) is not int or value <= 0:
        raise AIPersistenceModelValidationError(f"{field_name} must be a positive integer")
    return value


def _require_non_negative_int(value: Any, field_name: str) -> int:
    if type(value) is not int or value < 0:
        raise AIPersistenceModelValidationError(f"{field_name} must be a non-negative integer")
    return value


def _optional_positive_int(payload: Dict[str, Any], field_name: str, default: int) -> int:
    if field_name not in payload:
        return default
    return _require_positive_int(payload[field_name], field_name)


def _require_list(value: Any, field_name: str) -> List[Any]:
    if not isinstance(value, list):
        raise AIPersistenceModelValidationError(f"{field_name} must be a list")
    return value


def _optional_list(payload: Dict[str, Any], field_name: str, default: List[Any]) -> List[Any]:
    if field_name not in payload:
        return list(default)
    return _require_list(payload[field_name], field_name)


def _require_dict(value: Any, field_name: str) -> Dict[str, Any]:
    if not isinstance(value, dict):
        raise AIPersistenceModelValidationError(f"{field_name} must be a dictionary")
    return value


def _optional_dict(payload: Dict[str, Any], field_name: str, default: Dict[str, Any]) -> Dict[str, Any]:
    if field_name not in payload:
        return dict(default)
    return dict(_require_dict(payload[field_name], field_name))


def _optional_string(value: Any) -> Optional[str]:
    if value is None:
        return None
    if not isinstance(value, str):
        raise AIPersistenceModelValidationError("optional string fields must be strings")
    text = value.strip()
    return text if text else None


def _require_text_list(values: List[Any], field_name: str) -> None:
    for index, value in enumerate(values):
        _require_text(value, f"{field_name}[{index}]")


def _require_text_dict(values: Dict[str, Any], field_name: str) -> None:
    for key, value in values.items():
        _require_text(key, f"{field_name} key")
        _require_text(value, f"{field_name}.{key}")
