"""Assistant card widgets for mock response payloads."""

from __future__ import annotations

from typing import Any, Dict

from PySide6.QtWidgets import QFrame, QLabel, QVBoxLayout

from gui.styles.tokens import SPACING


CARD_OBJECT_NAMES = {
    "system_notice": "SystemNotice",
    "citation": "CitationCard",
    "search_result": "SearchResultCard",
    "plan": "PlanCard",
    "confirmation": "ConfirmationCard",
    "task_progress": "TaskProgressCard",
    "risk_notice": "RiskNoticeCard",
    "memory_candidate": "MemoryCandidateCard",
    "document_summary": "DocumentSummaryCard",
}


class AssistantCardWidget(QFrame):
    """Generic renderer for one assistant card contract."""

    def __init__(self, card: Dict[str, Any]):
        super().__init__()
        card_type = str(card.get("card_type") or "system_notice")
        self.card_type = card_type
        self.setObjectName(CARD_OBJECT_NAMES.get(card_type, "AssistantCard"))
        self.setProperty("assistantCardType", card_type)
        self.setMaximumWidth(340)

        title = QLabel(str(card.get("title") or ""))
        title.setObjectName("assistantCardTitle")
        title.setWordWrap(True)
        body = QLabel(str(card.get("body") or ""))
        body.setObjectName("assistantCardBody")
        body.setWordWrap(True)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(SPACING.compact, SPACING.compact, SPACING.compact, SPACING.compact)
        layout.setSpacing(6)
        layout.addWidget(title)
        if body.text():
            layout.addWidget(body)
        self._add_items(layout, card)
        self._add_citations(layout, card)
        self._add_actions(layout, card)

    @staticmethod
    def _add_items(layout: QVBoxLayout, card: Dict[str, Any]) -> None:
        for item in card.get("items") or []:
            label = QLabel(f"- {item}")
            label.setObjectName("assistantCardItem")
            label.setWordWrap(True)
            layout.addWidget(label)

    @staticmethod
    def _add_citations(layout: QVBoxLayout, card: Dict[str, Any]) -> None:
        for citation in card.get("citations") or []:
            title = citation.get("title") or citation.get("citation_id") or "citation"
            meta = " | ".join(
                str(value)
                for value in [
                    citation.get("layer"),
                    citation.get("status"),
                    citation.get("source_type"),
                    citation.get("confidence"),
                ]
                if value
            )
            text = f"{title}\n{meta}" if meta else str(title)
            label = QLabel(text)
            label.setObjectName("assistantCitationMeta")
            label.setWordWrap(True)
            layout.addWidget(label)

    @staticmethod
    def _add_actions(layout: QVBoxLayout, card: Dict[str, Any]) -> None:
        actions = card.get("actions") or []
        if not actions:
            return
        for action in actions:
            enabled = "可用" if action.get("enabled") else "不可用"
            label = QLabel(f"{action.get('label', '')}（{enabled}）")
            label.setObjectName("assistantActionText")
            label.setWordWrap(True)
            layout.addWidget(label)


def create_card_widget(card: Dict[str, Any]) -> AssistantCardWidget:
    return AssistantCardWidget(card)
