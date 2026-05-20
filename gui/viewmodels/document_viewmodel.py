"""Single-document preview ViewModel."""

from __future__ import annotations

from typing import Any, Dict


class DocumentViewModel:
    def __init__(self, adapter: Any):
        self.adapter = adapter
        self.document: Dict[str, Any] | None = None

    def open_document(self, document_id: int | str | None = None, path: str | None = None) -> Dict[str, Any]:
        self.document = self.adapter.open_document(document_id=document_id, path=path)
        return self.document
