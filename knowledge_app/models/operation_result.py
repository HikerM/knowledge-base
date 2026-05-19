"""Generic operation result model for service calls."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass(frozen=True)
class OperationResult:
    """Structured result wrapper shared by CLI and future GUI callers."""

    success: bool
    data: Optional[Any] = None
    warnings: List[str] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)
    elapsed_ms: int = 0

    def to_dict(self) -> Dict[str, Any]:
        payload: Dict[str, Any] = {
            "success": self.success,
            "warnings": list(self.warnings),
            "errors": list(self.errors),
            "elapsed_ms": self.elapsed_ms,
        }
        if self.data is not None:
            if hasattr(self.data, "to_dict"):
                payload["data"] = self.data.to_dict()
            else:
                payload["data"] = self.data
        return payload
