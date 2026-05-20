"""Qt StyleSheet generation for the light desktop theme."""

from __future__ import annotations

from gui.styles.tokens import BORDERS, COLORS, FONTS, RADIUS, SPACING


def build_light_qss() -> str:
    return f"""
* {{
    font-family: {FONTS.family};
    font-size: {FONTS.size}px;
    color: {COLORS.text_primary};
    selection-background-color: {COLORS.selected};
    selection-color: {COLORS.text_primary};
}}

QWidget {{
    background: {COLORS.app_bg};
}}

QLabel {{
    background: transparent;
}}

QFrame#topbar {{
    background: {COLORS.card_bg};
    border-bottom: {BORDERS.default};
}}

QFrame#sidebar {{
    background: {COLORS.card_bg};
    border-right: {BORDERS.default};
}}

QFrame#statusbar {{
    background: {COLORS.card_bg};
    border-top: {BORDERS.default};
}}

QLabel#sectionTitle {{
    font-size: {FONTS.title}px;
    font-weight: 700;
    color: {COLORS.text_primary};
}}

QLabel#sectionSubtitle,
QLabel#mutedText,
QLabel#pathLabel,
QLabel#cardCaption {{
    color: {COLORS.text_secondary};
}}

QLabel#cardTitle {{
    color: {COLORS.text_secondary};
    font-size: {FONTS.small}px;
    font-weight: 600;
}}

QLabel#cardValue {{
    color: {COLORS.text_primary};
    font-size: {FONTS.section}px;
    font-weight: 700;
}}

QLabel#emptyTitle {{
    color: {COLORS.text_primary};
    font-size: {FONTS.section}px;
    font-weight: 700;
}}

QLabel#errorTitle {{
    color: {COLORS.danger};
    font-size: {FONTS.section}px;
    font-weight: 700;
}}

QFrame#card {{
    background: {COLORS.card_bg};
    border: {BORDERS.default};
    border-radius: {RADIUS.medium}px;
}}

QFrame#softPanel {{
    background: {COLORS.subtle_bg};
    border: {BORDERS.default};
    border-radius: {RADIUS.medium}px;
}}

QLineEdit,
QComboBox,
QTextEdit,
QListWidget,
QTableWidget {{
    background: {COLORS.card_bg};
    border: {BORDERS.default};
    border-radius: {RADIUS.small}px;
}}

QLineEdit {{
    padding: 8px 11px;
}}

QComboBox {{
    padding: 7px 10px;
}}

QTextEdit {{
    padding: 10px;
    line-height: 1.45;
}}

QPushButton {{
    background: {COLORS.card_bg};
    border: {BORDERS.default};
    border-radius: {RADIUS.small}px;
    padding: 8px 12px;
    color: {COLORS.text_primary};
}}

QPushButton:hover {{
    border-color: {COLORS.border_strong};
    background: {COLORS.subtle_bg};
}}

QPushButton:focus,
QLineEdit:focus,
QComboBox:focus,
QTextEdit:focus,
QListWidget:focus,
QTableWidget:focus {{
    border: {BORDERS.focus};
}}

QPushButton:disabled {{
    color: {COLORS.text_muted};
    background: {COLORS.subtle_bg};
    border-color: {COLORS.border};
}}

QPushButton[buttonRole="primary"] {{
    background: {COLORS.primary};
    border-color: {COLORS.primary};
    color: white;
    font-weight: 600;
}}

QPushButton[buttonRole="primary"]:hover {{
    background: {COLORS.primary_hover};
    border-color: {COLORS.primary_hover};
}}

QPushButton[buttonRole="ghost"] {{
    background: transparent;
}}

QPushButton[navButton="true"] {{
    text-align: left;
    border: 0;
    background: transparent;
    padding: 10px 12px;
    color: {COLORS.text_secondary};
}}

QPushButton[navButton="true"]:hover {{
    background: {COLORS.subtle_bg};
    color: {COLORS.text_primary};
}}

QPushButton[navButton="true"]:checked {{
    background: {COLORS.selected};
    color: {COLORS.primary};
    font-weight: 700;
}}

QPushButton[navButton="true"]:disabled {{
    color: {COLORS.text_muted};
    background: transparent;
}}

QLabel#statusChip {{
    border-radius: {RADIUS.small}px;
    padding: 3px 8px;
    font-size: {FONTS.small}px;
    font-weight: 600;
}}

QLabel#statusChip[chipTone="ready"] {{
    background: {COLORS.success_bg};
    color: {COLORS.success};
}}

QLabel#statusChip[chipTone="warning"] {{
    background: {COLORS.warning_bg};
    color: {COLORS.warning};
}}

QLabel#statusChip[chipTone="danger"] {{
    background: {COLORS.danger_bg};
    color: {COLORS.danger};
}}

QLabel#statusChip[chipTone="info"] {{
    background: {COLORS.info_bg};
    color: {COLORS.info};
}}

QLabel#statusChip[chipTone="muted"] {{
    background: {COLORS.muted_bg};
    color: {COLORS.text_secondary};
}}

QListWidget {{
    padding: 6px;
    outline: 0;
}}

QListWidget::item {{
    border-radius: {RADIUS.small}px;
    padding: 9px;
    margin: 3px;
}}

QListWidget::item:selected {{
    background: {COLORS.selected};
    color: {COLORS.text_primary};
}}

QHeaderView::section {{
    background: {COLORS.subtle_bg};
    border: 0;
    border-bottom: {BORDERS.default};
    padding: 8px;
    color: {COLORS.text_secondary};
    font-weight: 600;
}}

QTableWidget {{
    gridline-color: {COLORS.border};
    alternate-background-color: {COLORS.subtle_bg};
    outline: 0;
}}

QTableWidget::item {{
    padding: 8px;
}}

QTableWidget::item:selected {{
    background: {COLORS.selected};
    color: {COLORS.text_primary};
}}

QSplitter::handle {{
    background: {COLORS.border};
}}

QScrollBar:vertical {{
    background: transparent;
    width: 10px;
}}

QScrollBar::handle:vertical {{
    background: {COLORS.border_strong};
    border-radius: 5px;
    min-height: 28px;
}}
""".strip()
