"""Markdown file, frontmatter, hashing, and chunking helpers."""

from __future__ import annotations

import hashlib
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from .frontmatter import frontmatter_text, parse_frontmatter


SEARCHABLE_EXTENSIONS = {".md", ".markdown"}
CHUNK_TARGET_CHARS = 1200
CHUNK_HARD_MAX_CHARS = 1500


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def normalized_hash_text(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip()


def read_single_markdown(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def markdown_text_from_bytes(value: bytes) -> str:
    return value.decode("utf-8").replace("\r\n", "\n").replace("\r", "\n")


def first_heading(body: str) -> Optional[str]:
    for line in body.splitlines():
        match = re.match(r"^\s*#{1,6}\s+(.+?)\s*$", line)
        if match:
            return match.group(1).strip()
    return None


def split_long_text(text: str, target: int = CHUNK_TARGET_CHARS) -> List[str]:
    text = text.strip()
    if len(text) <= CHUNK_HARD_MAX_CHARS:
        return [text] if text else []

    chunks: List[str] = []
    current: List[str] = []
    current_len = 0
    paragraphs = re.split(r"(\n\s*\n)", text)
    for part in paragraphs:
        if not part:
            continue
        if len(part) > CHUNK_HARD_MAX_CHARS:
            if current:
                chunks.append("".join(current).strip())
                current, current_len = [], 0
            for idx in range(0, len(part), target):
                segment = part[idx : idx + target].strip()
                if segment:
                    chunks.append(segment)
            continue
        if current_len + len(part) > target and current:
            chunks.append("".join(current).strip())
            current, current_len = [], 0
        current.append(part)
        current_len += len(part)
    if current:
        chunks.append("".join(current).strip())
    return [chunk for chunk in chunks if chunk]


def chunk_markdown(body: str, title: str) -> List[Dict[str, Any]]:
    sections: List[Tuple[str, str]] = []
    current_heading = title
    current_lines: List[str] = []

    def flush() -> None:
        nonlocal current_lines
        text = "\n".join(current_lines).strip()
        if text:
            sections.append((current_heading, text))
        current_lines = []

    for line in body.splitlines():
        match = re.match(r"^(#{1,6})\s+(.+?)\s*$", line)
        if match:
            flush()
            current_heading = match.group(2).strip()
            current_lines.append(line)
        else:
            current_lines.append(line)
    flush()

    if not sections:
        sections = [(title, body.strip() or title)]

    chunks: List[Dict[str, Any]] = []
    index = 0
    for heading, section_text in sections:
        for part in split_long_text(section_text):
            chunks.append(
                {
                    "chunk_index": index,
                    "heading": heading,
                    "content": part,
                    "token_estimate": max(1, len(part) // 4),
                }
            )
            index += 1
    return chunks


def read_markdown_parts(path: Path) -> Tuple[Dict[str, Any], str, bool]:
    text = read_single_markdown(path)
    return parse_frontmatter(text)


def write_markdown_parts(path: Path, meta: Dict[str, Any], body: str) -> None:
    path.write_text(frontmatter_text(meta) + body, encoding="utf-8", newline="\n")
