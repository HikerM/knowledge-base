#!/usr/bin/env python3
"""Validate application icon assets for Windows GUI packaging."""

from __future__ import annotations

import struct
import sys
from pathlib import Path


SOURCE_ROOT = Path(__file__).resolve().parents[1]
if str(SOURCE_ROOT) not in sys.path:
    sys.path.insert(0, str(SOURCE_ROOT))


ICON_DIR = SOURCE_ROOT / "assets" / "app-icon"
PNG_PATH = ICON_DIR / "app-icon.png"
ICO_PATH = ICON_DIR / "app-icon.ico"
REQUIRED_ICO_SIZES = {16, 32, 48, 256}
EXPECTED_ICO_SIZES = {16, 32, 48, 64, 128, 256}


def _load_qimage():
    try:
        from PySide6.QtGui import QImage
    except Exception as exc:  # noqa: BLE001
        raise AssertionError(f"PySide6 is required for icon validation: {exc}") from exc
    image = QImage(str(PNG_PATH))
    assert not image.isNull(), f"PNG icon cannot be loaded: {PNG_PATH}"
    return image


def _ico_sizes(data: bytes) -> set[int]:
    assert len(data) >= 6, "ICO file is too small"
    reserved, icon_type, count = struct.unpack_from("<HHH", data, 0)
    assert reserved == 0, "ICO reserved header must be 0"
    assert icon_type == 1, "ICO type must be 1"
    assert count >= len(REQUIRED_ICO_SIZES), "ICO should contain multiple image sizes"
    sizes: set[int] = set()
    offset = 6
    for _ in range(count):
        assert offset + 16 <= len(data), "ICO directory entry is truncated"
        width, height, color_count, reserved_byte, planes, bit_count, image_size, image_offset = struct.unpack_from("<BBBBHHII", data, offset)
        size = 256 if width == 0 else width
        height_size = 256 if height == 0 else height
        assert size == height_size, "ICO entries must be square"
        assert color_count == 0, "ICO entries should use true color"
        assert reserved_byte == 0, "ICO entry reserved byte must be 0"
        assert planes == 1, "ICO planes should be 1"
        assert bit_count == 32, "ICO entries should be 32-bit RGBA"
        assert image_size > 0, "ICO image payload is empty"
        assert 0 < image_offset < len(data), "ICO image offset is invalid"
        assert image_offset + image_size <= len(data), "ICO image payload is truncated"
        sizes.add(size)
        offset += 16
    return sizes


def main() -> int:
    assert PNG_PATH.exists(), "app-icon.png is missing"
    assert ICO_PATH.exists(), "app-icon.ico is missing"

    png_size = PNG_PATH.stat().st_size
    ico_size = ICO_PATH.stat().st_size
    assert 1_000 <= png_size <= 1_000_000, f"PNG icon size is suspicious: {png_size}"
    assert 1_000 <= ico_size <= 2_000_000, f"ICO icon size is suspicious: {ico_size}"

    image = _load_qimage()
    assert image.width() >= 256 and image.height() >= 256, "PNG icon should be high-resolution"
    assert image.hasAlphaChannel(), "PNG icon must include an alpha channel"

    transparent_samples = 0
    opaque_samples = 0
    for y in range(0, image.height(), max(1, image.height() // 16)):
        for x in range(0, image.width(), max(1, image.width() // 16)):
            alpha = image.pixelColor(x, y).alpha()
            if alpha == 0:
                transparent_samples += 1
            if alpha == 255:
                opaque_samples += 1
    assert transparent_samples > 0, "PNG icon must have transparent background pixels"
    assert opaque_samples > 0, "PNG icon must have visible opaque artwork"
    assert image.pixelColor(0, 0).alpha() == 0, "PNG icon must not use an opaque checkerboard corner"

    sizes = _ico_sizes(ICO_PATH.read_bytes())
    missing_required = REQUIRED_ICO_SIZES - sizes
    assert not missing_required, f"ICO missing required sizes: {sorted(missing_required)}"
    missing_expected = EXPECTED_ICO_SIZES - sizes
    assert not missing_expected, f"ICO missing expected sizes: {sorted(missing_expected)}"

    print(f"icon asset tests passed: ico sizes={sorted(sizes)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
