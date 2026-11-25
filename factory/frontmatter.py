"""Minimal front matter reader (stdlib only).

Supported subset of YAML, enough for tickets and prompts:
  key: value            str / int / true / false / null
  key: [a, "b c"]       inline list
  key:                  block list
    - item
Comment lines start with '#'. A trailing comment needs two spaces before '#' ('a: x  # note'),
so 'title: Fix #123' keeps its '#'. Integers with a leading zero stay strings ('0042').
Anything else raises FrontMatterError: the files are contracts, so they must parse exactly.
"""
from __future__ import annotations

import re
from pathlib import Path

_KEY = re.compile(r"^([A-Za-z_][A-Za-z0-9_-]*):(?:\s+(.*))?$")


class FrontMatterError(ValueError):
    pass


def _scalar(raw: str):
    raw = raw.strip()
    if not raw:
        return None
    if raw[0] in "\"'":
        if len(raw) < 2 or raw[-1] != raw[0]:
            raise FrontMatterError(f"unterminated quote: {raw}")
        return raw[1:-1]
    raw = re.split(r"\s{2,}#", raw, maxsplit=1)[0].strip()
    low = raw.lower()
    if low in ("null", "~", ""):
        return None
    if low == "true":
        return True
    if low == "false":
        return False
    if re.fullmatch(r"-?(0|[1-9]\d*)", raw):
        return int(raw)
    if raw.startswith("["):
        if not raw.endswith("]"):
            raise FrontMatterError(f"unterminated list: {raw}")
        inner = raw[1:-1].strip()
        if not inner:
            return []
        return [_scalar(part) for part in _split_inline(inner)]
    return raw


def _split_inline(inner: str) -> list[str]:
    parts, buf, quote = [], "", None
    for ch in inner:
        if quote:
            buf += ch
            if ch == quote:
                quote = None
        elif ch in "\"'":
            quote = ch
            buf += ch
        elif ch == ",":
            parts.append(buf)
            buf = ""
        else:
            buf += ch
    parts.append(buf)
    return [p.strip() for p in parts]


def split(text: str) -> tuple[dict, str]:
    """Return (front matter dict, body). Raises if the header is missing or malformed."""
    text = text.lstrip("﻿").replace("\r\n", "\n")
    if not text.startswith("---\n"):
        raise FrontMatterError("missing '---' front matter header")
    end = text.find("\n---", 3)
    if end == -1:
        raise FrontMatterError("missing closing '---'")
    header = text[4:end]
    body = text[end + 4:].lstrip("\n")
    return parse_header(header), body


def parse_header(header: str) -> dict:
    data: dict = {}
    current_list_key = None
    for lineno, line in enumerate(header.split("\n"), start=1):
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if stripped.startswith("- "):
            if current_list_key is None:
                raise FrontMatterError(f"line {lineno}: list item without a key")
            data[current_list_key].append(_scalar(stripped[2:]))
            continue
        if line[0].isspace():
            raise FrontMatterError(f"line {lineno}: nested mappings are not supported")
        m = _KEY.match(stripped)
        if not m:
            raise FrontMatterError(f"line {lineno}: cannot parse '{stripped}'")
        key, raw = m.group(1), m.group(2)
        if key in data:
            raise FrontMatterError(f"line {lineno}: duplicate key '{key}'")
        if raw is None or not raw.strip():
            data[key] = []
            current_list_key = key
        else:
            data[key] = _scalar(raw)
            current_list_key = None
    return data


def load(path: str | Path) -> tuple[dict, str]:
    return split(Path(path).read_text(encoding="utf-8-sig"))
