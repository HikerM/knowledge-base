"""Knowledge library summary ViewModel."""

from __future__ import annotations

from typing import Any, Dict


class LibraryViewModel:
    def __init__(self, adapter: Any):
        self.adapter = adapter
        self.summary: Dict[str, Any] | None = None

    def load_summary(
        self,
        limit: int = 50,
        offset: int = 0,
        layer: str | None = None,
        category_id: str | None = None,
    ) -> Dict[str, Any]:
        self.summary = self.adapter.load_library_summary(limit=limit, offset=offset, layer=layer, category_id=category_id)
        return self.summary
