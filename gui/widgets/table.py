"""Reusable read-only table helpers."""

from __future__ import annotations

from PySide6.QtWidgets import QAbstractItemView, QHeaderView, QTableWidget

from gui.styles.tokens import CONTROLS


class DataTable(QTableWidget):
    def __init__(self, rows: int, columns: int):
        super().__init__(rows, columns)
        self.setObjectName("dataTable")
        self.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.setSelectionMode(QAbstractItemView.SingleSelection)
        self.setAlternatingRowColors(True)
        self.setShowGrid(False)
        self.verticalHeader().setVisible(False)
        self.verticalHeader().setDefaultSectionSize(CONTROLS.table_row_height)
        self.horizontalHeader().setMinimumHeight(CONTROLS.table_header_height)
        self.horizontalHeader().setSectionResizeMode(QHeaderView.Interactive)
