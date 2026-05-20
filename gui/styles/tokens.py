"""Design tokens for the light PySide6 desktop theme."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ColorTokens:
    app_bg: str = "#F6F8FB"
    card_bg: str = "#FFFFFF"
    subtle_bg: str = "#F1F5F9"
    border: str = "#E2E8F0"
    border_strong: str = "#CBD5E1"
    text_primary: str = "#1E293B"
    text_secondary: str = "#64748B"
    text_muted: str = "#94A3B8"
    primary: str = "#2563EB"
    primary_hover: str = "#1D4ED8"
    selected: str = "#DBEAFE"
    selected_border: str = "#93C5FD"
    success: str = "#16A34A"
    success_bg: str = "#DCFCE7"
    warning: str = "#D97706"
    warning_bg: str = "#FEF3C7"
    danger: str = "#DC2626"
    danger_bg: str = "#FEE2E2"
    info: str = "#0284C7"
    info_bg: str = "#E0F2FE"
    muted_bg: str = "#F1F5F9"


@dataclass(frozen=True)
class FontTokens:
    family: str = '"Microsoft YaHei UI", "Microsoft YaHei", "Segoe UI", system-ui'
    size: int = 13
    small: int = 12
    title: int = 22
    section: int = 17


@dataclass(frozen=True)
class SpacingTokens:
    page: int = 24
    card: int = 16
    compact: int = 8
    gap: int = 12
    shell: int = 16


@dataclass(frozen=True)
class RadiusTokens:
    small: int = 8
    medium: int = 10
    large: int = 12
    pill: int = 999


@dataclass(frozen=True)
class BorderTokens:
    default: str = "1px solid #E2E8F0"
    focus: str = "1px solid #93C5FD"


COLORS = ColorTokens()
FONTS = FontTokens()
SPACING = SpacingTokens()
RADIUS = RadiusTokens()
BORDERS = BorderTokens()

