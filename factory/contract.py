"""Ticket contract: validation, acceptance-test ids, and the authoritative copy kept in the journal.

The copy in the worktree (.factory/ticket.md) is only for the agent to read. Gates and merge use
<journal>/<ID>/contract.md, written by 'start' or 'amend' (human commands), and refuse when the
worktree copy no longer matches its sha256.
"""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

import frontmatter

ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$")
TEST_ID_RE = re.compile(r"^[A-Za-z0-9_./:\[\]-]+$")
AC_LINE = re.compile(r"^\s*-\s*AC-\d+\s*:", re.M)
AC_TEST = re.compile(r"Test:\s*`([^`]+)`")
REQUIRED = ["id", "title", "area", "type", "allowed_paths", "status"]
LISTS = ["allowed_paths", "forbidden_paths", "new_dependencies", "unlock"]
INTS = ["max_diff_lines", "attempts_max"]


def sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def ac_tests(body: str) -> list[str]:
    return AC_TEST.findall(body)


def _bad_glob(g) -> str | None:
    if not isinstance(g, str) or not g:
        return "empty or not a string"
    if g[0] in "*?[":
        return "must start with a literal directory or file name"
    if g.startswith(("/", "~")) or re.match(r"^[A-Za-z]:", g) or "\\" in g:
        return "must be relative, with '/' separators"
    if ".." in g.split("/"):
        return "must not contain '..'"
    return None


def validate(t: dict, body: str, policy: dict) -> list[str]:
    errs = [f"missing field: {k}" for k in REQUIRED if not t.get(k)]
    tid = t.get("id")
    if tid is not None and not (isinstance(tid, str) and ID_RE.match(tid)):
        errs.append(f"id {tid!r} must be a string of [A-Za-z0-9._-] (it becomes a branch and a folder)")
    if t.get("status") and t["status"] != "ready":
        errs.append(f"status is {t['status']!r}; only 'ready' tickets can start")
    if t.get("type") and t["type"] not in policy.get("ticket_types", []):
        errs.append(f"type {t['type']!r} not in {policy.get('ticket_types')}")
    for k in LISTS:
        if k in t and t[k] is not None and not isinstance(t[k], list):
            errs.append(f"{k} must be a list")
    for k in INTS:
        if k in t and t[k] is not None and (not isinstance(t[k], int) or t[k] < 1):
            errs.append(f"{k} must be a positive integer")
    for g in t.get("allowed_paths") or []:
        why = _bad_glob(g)
        if why:
            errs.append(f"allowed_paths {g!r}: {why}")
    for p in t.get("unlock") or []:
        if not isinstance(p, str) or re.search(r"[*?\[]", p) or _bad_glob(p):
            errs.append(f"unlock {p!r}: must be one exact relative path, no wildcard")
    ac_lines = AC_LINE.findall(body)
    if not ac_lines:
        errs.append("no acceptance criterion ('- AC-1: ...') in the body")
    for line in body.splitlines():
        if AC_LINE.match(line) and not AC_TEST.search(line):
            errs.append(f"criterion without a test: {line.strip()[:80]}")
    for test in ac_tests(body):
        if not TEST_ID_RE.match(test) or test.startswith("-"):
            errs.append(f"test id {test!r} has characters outside [A-Za-z0-9_./:[]-]")
    return errs


def ticket_dir(journal: str | Path, tid: str) -> Path:
    if not ID_RE.match(tid):
        raise SystemExit(f"invalid ticket id {tid!r}")
    d = Path(journal) / tid
    d.mkdir(parents=True, exist_ok=True)
    return d


def store(journal: str | Path, ticket_text: str, state: dict) -> dict:
    fm, _ = frontmatter.split(ticket_text)
    d = ticket_dir(journal, fm["id"])
    (d / "contract.md").write_text(ticket_text, encoding="utf-8")
    state = dict(state, contract_sha256=sha256(ticket_text))
    (d / "state.json").write_text(json.dumps(state, indent=2), encoding="utf-8")
    return state


def load(journal: str | Path, tid: str) -> tuple[dict, str, dict]:
    d = ticket_dir(journal, tid)
    if not (d / "state.json").exists():
        raise SystemExit(f"no contract for {tid} in {d}: was it started with fx.py start?")
    text = (d / "contract.md").read_text(encoding="utf-8")
    fm, body = frontmatter.split(text)
    return fm, body, json.loads((d / "state.json").read_text(encoding="utf-8"))
