"""Static local model catalog loader and schema validation.

This module parses the design-only local model catalog. It does not download
models, open network connections, start runtimes, or create provider objects.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

import yaml


LOCAL_MODEL_CATALOG_SCHEMA_VERSION = "local-model-catalog-v0.1"
ALLOWED_SOURCE_KINDS = {"modelscope_reference", "manual_reference"}
DEFAULT_MODEL_ID = "qwen3_0_6b_gguf_q4_k_m"
DEFAULT_MODEL_DISPLAY_NAME = "Qwen3-0.6B-GGUF Q4_K_M"
MAX_DEFAULT_EXPECTED_SIZE_GB = 1.0
REJECT_DEFAULT_SIZE_GB = 30.0


class LocalModelCatalogValidationError(ValueError):
    """Raised when the local model catalog violates the static contract."""


class LocalModelTier(str, Enum):
    """Allowed local model catalog tiers."""

    ULTRA_LIGHT = "ultra_light"
    LIGHT = "light"
    STANDARD = "standard"
    HIGH_QUALITY = "high_quality"


@dataclass(frozen=True)
class LocalModelEntry:
    """One static catalog entry for a reference-only local model file."""

    id: str
    model_id: str
    display_name: str
    tier: LocalModelTier
    filename: str
    source_kind: str
    source_ref: str
    provider_kind: str
    quantization: str
    expected_size: float
    install_size: float
    sha256: str
    verified_install_allowed: bool
    min_ram_gb: float
    recommended_ram_gb: float
    gpu_required: bool
    default: bool
    suitable_for: List[str] = field(default_factory=list)
    not_suitable_for: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    raw: Dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, payload: Dict[str, Any], index: int) -> "LocalModelEntry":
        _require_dict(payload, f"models[{index}]")
        _require_model_fields(payload, index)
        source_kind, source_ref = _source_from_payload(payload, index)
        return cls(
            id=_require_text(payload.get("id"), f"models[{index}].id"),
            model_id=_require_text(payload.get("model_id"), f"models[{index}].model_id"),
            display_name=_require_text(payload.get("display_name"), f"models[{index}].display_name"),
            tier=_tier_from_value(payload.get("tier"), f"models[{index}].tier"),
            filename=_require_text(payload.get("filename"), f"models[{index}].filename"),
            source_kind=source_kind,
            source_ref=source_ref,
            provider_kind=_require_text(payload.get("provider_kind"), f"models[{index}].provider_kind"),
            quantization=_require_text(payload.get("quantization"), f"models[{index}].quantization"),
            expected_size=_number_from_aliases(
                payload,
                ["expected_size_gb", "expected_size"],
                f"models[{index}].expected_size",
            ),
            install_size=_number_from_aliases(
                payload,
                ["install_size_gb", "install_size"],
                f"models[{index}].install_size",
            ),
            sha256=_require_text(payload.get("sha256"), f"models[{index}].sha256"),
            verified_install_allowed=_bool_from_aliases(
                payload,
                ["verified_install_allowed"],
                f"models[{index}].verified_install_allowed",
            ),
            min_ram_gb=_number_from_aliases(
                payload,
                ["min_ram_gb", "minimum_ram_gb"],
                f"models[{index}].min_ram_gb",
            ),
            recommended_ram_gb=_number_from_aliases(
                payload,
                ["recommended_ram_gb"],
                f"models[{index}].recommended_ram_gb",
            ),
            gpu_required=_bool_from_aliases(
                payload,
                ["gpu_required", "requires_gpu"],
                f"models[{index}].gpu_required",
            ),
            default=_bool_from_aliases(
                payload,
                ["default", "is_default"],
                f"models[{index}].default",
            ),
            suitable_for=_list_from_aliases(
                payload,
                ["suitable_for", "suitable_tasks"],
                f"models[{index}].suitable_for",
            ),
            not_suitable_for=_list_from_aliases(
                payload,
                ["not_suitable_for", "unsuitable_tasks"],
                f"models[{index}].not_suitable_for",
            ),
            warnings=_list_from_aliases(
                payload,
                ["warnings", "risk_notice"],
                f"models[{index}].warnings",
            ),
            raw=dict(payload),
        ).validate()

    def validate(self) -> "LocalModelEntry":
        _require_text(self.id, "model.id")
        _require_text(self.model_id, f"{self.id}.model_id")
        _require_text(self.display_name, f"{self.id}.display_name")
        if not isinstance(self.tier, LocalModelTier):
            raise LocalModelCatalogValidationError(f"{self.id}: tier must be a LocalModelTier")
        _require_text(self.filename, f"{self.id}.filename")
        _require_text(self.source_kind, f"{self.id}.source_kind")
        _require_text(self.source_ref, f"{self.id}.source_ref")
        _require_text(self.provider_kind, f"{self.id}.provider_kind")
        _require_text(self.quantization, f"{self.id}.quantization")
        _require_positive_number(self.expected_size, f"{self.id}.expected_size")
        _require_positive_number(self.install_size, f"{self.id}.install_size")
        _require_text(self.sha256, f"{self.id}.sha256")
        _require_bool(self.verified_install_allowed, f"{self.id}.verified_install_allowed")
        _require_positive_number(self.min_ram_gb, f"{self.id}.min_ram_gb")
        _require_positive_number(self.recommended_ram_gb, f"{self.id}.recommended_ram_gb")
        _require_bool(self.gpu_required, f"{self.id}.gpu_required")
        _require_bool(self.default, f"{self.id}.default")
        _require_text_list(self.suitable_for, f"{self.id}.suitable_for")
        _require_text_list(self.not_suitable_for, f"{self.id}.not_suitable_for")
        _require_text_list(self.warnings, f"{self.id}.warnings")

        if self.provider_kind != "local":
            raise LocalModelCatalogValidationError(f"{self.id}: provider_kind must be local")
        if not self.filename.lower().endswith(".gguf"):
            raise LocalModelCatalogValidationError(f"{self.id}: filename must be a .gguf file")
        if self.source_kind not in ALLOWED_SOURCE_KINDS:
            allowed = ", ".join(sorted(ALLOWED_SOURCE_KINDS))
            raise LocalModelCatalogValidationError(f"{self.id}: source_kind must be one of: {allowed}")
        if self.sha256 == "pending" and self.verified_install_allowed:
            raise LocalModelCatalogValidationError(f"{self.id}: sha256=pending blocks verified install")
        if self.verified_install_allowed and self.sha256 == "pending":
            raise LocalModelCatalogValidationError(f"{self.id}: verified install requires sha256")
        if self.verified_install_allowed and not self.sha256.strip():
            raise LocalModelCatalogValidationError(f"{self.id}: verified install requires sha256")
        if self.recommended_ram_gb < self.min_ram_gb:
            raise LocalModelCatalogValidationError(f"{self.id}: recommended_ram_gb must be >= min_ram_gb")
        return self

    def to_dict(self) -> Dict[str, Any]:
        self.validate()
        return {
            "id": self.id,
            "model_id": self.model_id,
            "display_name": self.display_name,
            "tier": self.tier.value,
            "filename": self.filename,
            "source_kind": self.source_kind,
            "source_ref": self.source_ref,
            "provider_kind": self.provider_kind,
            "quantization": self.quantization,
            "expected_size": self.expected_size,
            "install_size": self.install_size,
            "sha256": self.sha256,
            "verified_install_allowed": self.verified_install_allowed,
            "min_ram_gb": self.min_ram_gb,
            "recommended_ram_gb": self.recommended_ram_gb,
            "gpu_required": self.gpu_required,
            "default": self.default,
            "suitable_for": list(self.suitable_for),
            "not_suitable_for": list(self.not_suitable_for),
            "warnings": list(self.warnings),
        }


@dataclass(frozen=True)
class LocalModelStoragePolicy:
    """Static storage policy for future local model files."""

    default_model_dir_windows: str
    user_custom_model_dir_allowed: bool
    forbidden_locations: List[str]
    uninstall_app_deletes_models_by_default: bool
    user_can_delete_model_files_in_settings: bool
    user_custom_dir_requires_future_confirmation: bool = True
    delete_model_requires_confirmation: bool = True

    @classmethod
    def from_dict(cls, payload: Dict[str, Any]) -> "LocalModelStoragePolicy":
        _require_dict(payload, "storage_policy")
        _require_keys(
            payload,
            [
                "default_model_dir_windows",
                "user_custom_model_dir_allowed",
                "forbidden_locations",
                "uninstall_app_deletes_models_by_default",
                "user_can_delete_model_files_in_settings",
            ],
            "storage_policy",
        )
        return cls(
            default_model_dir_windows=_require_text(
                payload.get("default_model_dir_windows"),
                "storage_policy.default_model_dir_windows",
            ),
            user_custom_model_dir_allowed=_require_bool(
                payload.get("user_custom_model_dir_allowed"),
                "storage_policy.user_custom_model_dir_allowed",
            ),
            forbidden_locations=_require_text_list(
                _require_list(payload.get("forbidden_locations"), "storage_policy.forbidden_locations"),
                "storage_policy.forbidden_locations",
            ),
            uninstall_app_deletes_models_by_default=_require_bool(
                payload.get("uninstall_app_deletes_models_by_default"),
                "storage_policy.uninstall_app_deletes_models_by_default",
            ),
            user_can_delete_model_files_in_settings=_require_bool(
                payload.get("user_can_delete_model_files_in_settings"),
                "storage_policy.user_can_delete_model_files_in_settings",
            ),
            user_custom_dir_requires_future_confirmation=_optional_bool(
                payload,
                "user_custom_dir_requires_future_confirmation",
                True,
            ),
            delete_model_requires_confirmation=_optional_bool(
                payload,
                "delete_model_requires_confirmation",
                True,
            ),
        ).validate()

    def validate(self) -> "LocalModelStoragePolicy":
        _require_text(self.default_model_dir_windows, "storage_policy.default_model_dir_windows")
        _require_bool(self.user_custom_model_dir_allowed, "storage_policy.user_custom_model_dir_allowed")
        _require_text_list(self.forbidden_locations, "storage_policy.forbidden_locations")
        _require_bool(
            self.uninstall_app_deletes_models_by_default,
            "storage_policy.uninstall_app_deletes_models_by_default",
        )
        _require_bool(
            self.user_can_delete_model_files_in_settings,
            "storage_policy.user_can_delete_model_files_in_settings",
        )
        _require_bool(
            self.user_custom_dir_requires_future_confirmation,
            "storage_policy.user_custom_dir_requires_future_confirmation",
        )
        _require_bool(
            self.delete_model_requires_confirmation,
            "storage_policy.delete_model_requires_confirmation",
        )
        return self


@dataclass(frozen=True)
class LocalModelDownloadPolicy:
    """Static download policy gates for future installer work."""

    no_auto_download: bool
    confirmation_required: bool
    task_queue_required: bool
    single_file_gguf_only: bool
    no_repository_download: bool
    no_shell_script: bool
    no_arbitrary_command: bool
    actual_download_enabled: bool = False

    @classmethod
    def from_dict(cls, payload: Dict[str, Any]) -> "LocalModelDownloadPolicy":
        _require_dict(payload, "download_policy")
        _require_keys(
            payload,
            [
                "single_file_gguf_only",
                "user_confirmation_required",
                "task_queue_required",
            ],
            "download_policy",
        )
        actual_download_enabled = _optional_bool(payload, "actual_download_enabled", False)
        whole_repository_download_allowed = _optional_bool(payload, "whole_repository_download_allowed", False)
        shell_download_script_allowed = _optional_bool(payload, "shell_download_script_allowed", False)
        arbitrary_command_allowed = _optional_bool(payload, "arbitrary_command_allowed", False)
        return cls(
            no_auto_download=_optional_bool(payload, "no_auto_download", not actual_download_enabled),
            confirmation_required=_optional_bool(
                payload,
                "confirmation_required",
                _require_bool(payload.get("user_confirmation_required"), "download_policy.user_confirmation_required"),
            ),
            task_queue_required=_require_bool(payload.get("task_queue_required"), "download_policy.task_queue_required"),
            single_file_gguf_only=_require_bool(
                payload.get("single_file_gguf_only"),
                "download_policy.single_file_gguf_only",
            ),
            no_repository_download=_optional_bool(
                payload,
                "no_repository_download",
                not whole_repository_download_allowed,
            ),
            no_shell_script=_optional_bool(payload, "no_shell_script", not shell_download_script_allowed),
            no_arbitrary_command=_optional_bool(payload, "no_arbitrary_command", not arbitrary_command_allowed),
            actual_download_enabled=actual_download_enabled,
        ).validate()

    def validate(self) -> "LocalModelDownloadPolicy":
        for field_name in [
            "no_auto_download",
            "confirmation_required",
            "task_queue_required",
            "single_file_gguf_only",
            "no_repository_download",
            "no_shell_script",
            "no_arbitrary_command",
            "actual_download_enabled",
        ]:
            _require_bool(getattr(self, field_name), f"download_policy.{field_name}")
        return self


@dataclass(frozen=True)
class LocalModelVerificationPolicy:
    """Static verification policy for future verified installs."""

    sha256_required_for_verified_install: bool
    sha256_pending_blocks_verified_install: bool
    expected_size_required: bool
    invalid_checksum_fails_install: bool
    license_review_required: bool

    @classmethod
    def from_dict(cls, payload: Dict[str, Any]) -> "LocalModelVerificationPolicy":
        _require_dict(payload, "verification_policy")
        _require_keys(
            payload,
            [
                "sha256_required_for_verified_install",
                "sha256_pending_blocks_verified_install",
                "expected_size_required",
                "invalid_checksum_fails_install",
                "license_review_required",
            ],
            "verification_policy",
        )
        return cls(
            sha256_required_for_verified_install=_require_bool(
                payload.get("sha256_required_for_verified_install"),
                "verification_policy.sha256_required_for_verified_install",
            ),
            sha256_pending_blocks_verified_install=_require_bool(
                payload.get("sha256_pending_blocks_verified_install"),
                "verification_policy.sha256_pending_blocks_verified_install",
            ),
            expected_size_required=_require_bool(
                payload.get("expected_size_required"),
                "verification_policy.expected_size_required",
            ),
            invalid_checksum_fails_install=_require_bool(
                payload.get("invalid_checksum_fails_install"),
                "verification_policy.invalid_checksum_fails_install",
            ),
            license_review_required=_require_bool(
                payload.get("license_review_required"),
                "verification_policy.license_review_required",
            ),
        ).validate()

    def validate(self) -> "LocalModelVerificationPolicy":
        for field_name in [
            "sha256_required_for_verified_install",
            "sha256_pending_blocks_verified_install",
            "expected_size_required",
            "invalid_checksum_fails_install",
            "license_review_required",
        ]:
            _require_bool(getattr(self, field_name), f"verification_policy.{field_name}")
        return self


@dataclass(frozen=True)
class LocalModelCatalog:
    """Validated static local model catalog."""

    schema_version: str
    default_model: str
    tiers: Dict[LocalModelTier, Dict[str, Any]]
    models: List[LocalModelEntry]
    storage_policy: LocalModelStoragePolicy
    download_policy: LocalModelDownloadPolicy
    verification_policy: LocalModelVerificationPolicy
    stage: str = "design_only"
    raw: Dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, payload: Dict[str, Any]) -> "LocalModelCatalog":
        _require_dict(payload, "local model catalog")
        _require_keys(
            payload,
            [
                "schema_version",
                "default_model",
                "tiers",
                "models",
                "storage_policy",
                "download_policy",
                "verification_policy",
            ],
            "local model catalog",
        )
        models_payload = _require_list(payload.get("models"), "models")
        models = [LocalModelEntry.from_dict(item, index) for index, item in enumerate(models_payload)]
        return cls(
            schema_version=_require_text(payload.get("schema_version"), "schema_version"),
            stage=str(payload.get("stage") or "design_only"),
            default_model=_require_text(payload.get("default_model"), "default_model"),
            tiers=_tiers_from_payload(payload.get("tiers")),
            models=models,
            storage_policy=LocalModelStoragePolicy.from_dict(payload["storage_policy"]),
            download_policy=LocalModelDownloadPolicy.from_dict(payload["download_policy"]),
            verification_policy=LocalModelVerificationPolicy.from_dict(payload["verification_policy"]),
            raw=dict(payload),
        ).validate()

    def validate(self) -> "LocalModelCatalog":
        _require_text(self.schema_version, "schema_version")
        _require_text(self.stage, "stage")
        _require_text(self.default_model, "default_model")
        _require_dict(self.tiers, "tiers")
        _require_list(self.models, "models")
        if self.schema_version != LOCAL_MODEL_CATALOG_SCHEMA_VERSION:
            raise LocalModelCatalogValidationError("unsupported local model catalog schema_version")
        if self.stage != "design_only":
            raise LocalModelCatalogValidationError("local model catalog must remain design_only")
        _validate_tiers(self.tiers)
        self.storage_policy.validate()
        self.download_policy.validate()
        self.verification_policy.validate()
        _validate_model_collection(self.models)
        _validate_default_model(self)
        return self


def load_local_model_catalog(path: Path | str) -> LocalModelCatalog:
    """Load a local model catalog YAML file and return a validated catalog."""

    catalog_path = Path(path)
    try:
        payload = yaml.safe_load(catalog_path.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        raise LocalModelCatalogValidationError(f"invalid local model catalog YAML: {exc}") from exc
    except OSError as exc:
        raise LocalModelCatalogValidationError(f"could not read local model catalog: {catalog_path}: {exc}") from exc
    return validate_local_model_catalog(payload)


def validate_local_model_catalog(catalog: LocalModelCatalog | Dict[str, Any]) -> LocalModelCatalog:
    """Validate a parsed catalog mapping or catalog object."""

    if isinstance(catalog, LocalModelCatalog):
        return catalog.validate()
    return LocalModelCatalog.from_dict(catalog)


def get_default_model(catalog: LocalModelCatalog) -> LocalModelEntry:
    """Return the single default model."""

    validate_local_model_catalog(catalog)
    return get_model(catalog, catalog.default_model)


def list_models_by_tier(catalog: LocalModelCatalog, tier: LocalModelTier | str) -> List[LocalModelEntry]:
    """List models in a validated catalog by tier."""

    validate_local_model_catalog(catalog)
    resolved_tier = _tier_from_value(tier, "tier")
    return [model for model in catalog.models if model.tier == resolved_tier]


def get_model(catalog: LocalModelCatalog, model_id: str) -> LocalModelEntry:
    """Return a model by catalog id."""

    validate_local_model_catalog(catalog)
    wanted = _require_text(model_id, "model_id")
    for model in catalog.models:
        if model.id == wanted:
            return model
    raise LocalModelCatalogValidationError(f"unknown local model id: {wanted}")


def _validate_model_collection(models: Iterable[LocalModelEntry]) -> None:
    seen_ids: set[str] = set()
    for model in models:
        if not isinstance(model, LocalModelEntry):
            raise LocalModelCatalogValidationError("models must contain LocalModelEntry objects")
        model.validate()
        if model.id in seen_ids:
            raise LocalModelCatalogValidationError(f"duplicate local model id: {model.id}")
        seen_ids.add(model.id)


def _validate_default_model(catalog: LocalModelCatalog) -> None:
    model_by_id = {model.id: model for model in catalog.models}
    default = model_by_id.get(catalog.default_model)
    if default is None:
        raise LocalModelCatalogValidationError("default_model must reference an existing model")

    flagged_defaults = [model for model in catalog.models if model.default]
    if len(flagged_defaults) != 1:
        raise LocalModelCatalogValidationError("local model catalog must declare exactly one default model")
    if flagged_defaults[0].id != catalog.default_model:
        raise LocalModelCatalogValidationError("default flag must match default_model")
    if default.tier is not LocalModelTier.ULTRA_LIGHT:
        raise LocalModelCatalogValidationError("default model tier must be ultra_light")
    if default.display_name != DEFAULT_MODEL_DISPLAY_NAME:
        raise LocalModelCatalogValidationError("default model must stay Qwen3-0.6B-GGUF Q4_K_M")
    if default.expected_size > MAX_DEFAULT_EXPECTED_SIZE_GB and default.tier is not LocalModelTier.ULTRA_LIGHT:
        raise LocalModelCatalogValidationError("default model must be <= 1GB or explicitly ultra_light")
    if default.expected_size >= REJECT_DEFAULT_SIZE_GB or default.install_size >= REJECT_DEFAULT_SIZE_GB:
        raise LocalModelCatalogValidationError("30GB+ models cannot be default")


def _validate_tiers(tiers: Dict[LocalModelTier, Dict[str, Any]]) -> None:
    required = set(LocalModelTier)
    present = set(tiers)
    missing = required.difference(present)
    if missing:
        values = ", ".join(sorted(tier.value for tier in missing))
        raise LocalModelCatalogValidationError(f"tiers missing required entries: {values}")


def _tiers_from_payload(payload: Any) -> Dict[LocalModelTier, Dict[str, Any]]:
    raw_tiers = _require_dict(payload, "tiers")
    tiers: Dict[LocalModelTier, Dict[str, Any]] = {}
    for key, value in raw_tiers.items():
        tier = _tier_from_value(key, f"tiers.{key}")
        if tier in tiers:
            raise LocalModelCatalogValidationError(f"duplicate tier: {tier.value}")
        tiers[tier] = dict(_require_dict(value, f"tiers.{tier.value}"))
    return tiers


def _require_model_fields(payload: Dict[str, Any], index: int) -> None:
    required = [
        "id",
        "model_id",
        "display_name",
        "tier",
        "filename",
        "provider_kind",
        "quantization",
        "sha256",
        "verified_install_allowed",
        "recommended_ram_gb",
    ]
    missing = [key for key in required if key not in payload]
    if "expected_size_gb" not in payload and "expected_size" not in payload:
        missing.append("expected_size")
    if "install_size_gb" not in payload and "install_size" not in payload:
        missing.append("install_size")
    if "min_ram_gb" not in payload and "minimum_ram_gb" not in payload:
        missing.append("min_ram_gb")
    if "gpu_required" not in payload and "requires_gpu" not in payload:
        missing.append("gpu_required")
    if "default" not in payload and "is_default" not in payload:
        missing.append("default")
    if "suitable_for" not in payload and "suitable_tasks" not in payload:
        missing.append("suitable_for")
    if "not_suitable_for" not in payload and "unsuitable_tasks" not in payload:
        missing.append("not_suitable_for")
    if "warnings" not in payload and "risk_notice" not in payload:
        missing.append("warnings")
    if "source_ref" not in payload and "modelscope_reference" not in payload and "manual_reference" not in payload:
        missing.append("source_ref")
    if missing:
        raise LocalModelCatalogValidationError(f"models[{index}] missing required fields: {', '.join(sorted(missing))}")


def _source_from_payload(payload: Dict[str, Any], index: int) -> tuple[str, str]:
    raw_source_kind = payload.get("source_kind")
    raw_source_ref = payload.get("source_ref")
    if raw_source_kind is not None or raw_source_ref is not None:
        return (
            _require_text(raw_source_kind, f"models[{index}].source_kind"),
            _require_text(raw_source_ref, f"models[{index}].source_ref"),
        )
    if payload.get("modelscope_reference"):
        return (
            "modelscope_reference",
            _require_text(payload.get("modelscope_reference"), f"models[{index}].modelscope_reference"),
        )
    if payload.get("manual_reference"):
        return (
            "manual_reference",
            _require_text(payload.get("manual_reference"), f"models[{index}].manual_reference"),
        )
    raise LocalModelCatalogValidationError(f"models[{index}] source_ref is required")


def _tier_from_value(value: Any, field_name: str) -> LocalModelTier:
    text = _require_text(value, field_name)
    try:
        return LocalModelTier(text)
    except ValueError as exc:
        allowed = ", ".join(tier.value for tier in LocalModelTier)
        raise LocalModelCatalogValidationError(f"{field_name} must be one of: {allowed}") from exc


def _require_keys(payload: Dict[str, Any], keys: List[str], model_name: str) -> None:
    _require_dict(payload, model_name)
    missing = [key for key in keys if key not in payload]
    if missing:
        raise LocalModelCatalogValidationError(f"{model_name} missing required fields: {', '.join(missing)}")


def _number_from_aliases(payload: Dict[str, Any], names: List[str], field_name: str) -> float:
    for name in names:
        if name in payload:
            return _require_positive_number(payload[name], field_name)
    raise LocalModelCatalogValidationError(f"{field_name} is required")


def _bool_from_aliases(payload: Dict[str, Any], names: List[str], field_name: str) -> bool:
    for name in names:
        if name in payload:
            return _require_bool(payload[name], field_name)
    raise LocalModelCatalogValidationError(f"{field_name} is required")


def _list_from_aliases(payload: Dict[str, Any], names: List[str], field_name: str) -> List[str]:
    for name in names:
        if name in payload:
            return _require_text_list(_require_list(payload[name], field_name), field_name)
    raise LocalModelCatalogValidationError(f"{field_name} is required")


def _optional_bool(payload: Dict[str, Any], field_name: str, default: bool) -> bool:
    if field_name not in payload:
        return default
    return _require_bool(payload[field_name], field_name)


def _require_text(value: Any, field_name: str) -> str:
    if value is None or not isinstance(value, str) or not value.strip():
        raise LocalModelCatalogValidationError(f"{field_name} is required")
    return value.strip()


def _require_bool(value: Any, field_name: str) -> bool:
    if type(value) is not bool:
        raise LocalModelCatalogValidationError(f"{field_name} must be a boolean")
    return value


def _require_positive_number(value: Any, field_name: str) -> float:
    if type(value) not in {int, float} or value <= 0:
        raise LocalModelCatalogValidationError(f"{field_name} must be a positive number")
    return float(value)


def _require_list(value: Any, field_name: str) -> List[Any]:
    if not isinstance(value, list):
        raise LocalModelCatalogValidationError(f"{field_name} must be a list")
    return value


def _require_dict(value: Any, field_name: str) -> Dict[Any, Any]:
    if not isinstance(value, dict):
        raise LocalModelCatalogValidationError(f"{field_name} must be a mapping")
    return value


def _require_text_list(values: List[Any], field_name: str) -> List[str]:
    result: List[str] = []
    for index, item in enumerate(values):
        result.append(_require_text(item, f"{field_name}[{index}]"))
    return result
