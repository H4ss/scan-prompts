#!/usr/bin/env python3
"""Lint this prompt repository: file names, front matter, lifecycle, supersedes chain.

Run before every commit: python3 factory/lint_prompts.py
"""
from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import frontmatter  # noqa: E402

NAME = re.compile(r"^(\d{4}-\d{2}-\d{2})-(\d{2})-([a-z0-9]+(?:-[a-z0-9]+)*)\.md$")
STATUSES = {"draft", "ready", "applied", "superseded", "withdrawn"}
TARGETS = {"factory-dev", "factory-review", "opencode-plan", "human"}
REQUIRED = ["id", "date", "version", "contract", "target", "tickets", "status", "supersedes"]
FROZEN = {"ready", "applied", "superseded", "withdrawn"}
STATUS_LINE = re.compile(r"^status:.*$", re.M)


def committed(root: Path, rel: str):
    """Text of the file at HEAD, or None (new file, or not a git repo)."""
    res = subprocess.run(["git", "show", f"HEAD:{rel}"], cwd=root, capture_output=True,
                         text=True, encoding="utf-8", errors="replace")
    return res.stdout if res.returncode == 0 else None


def lint(root: Path) -> list[str]:
    errs: list[str] = []
    prompts = sorted((root / "prompts").glob("*.md"))
    ids: dict[str, dict] = {}
    for f in prompts:
        m = NAME.match(f.name)
        if not m:
            errs.append(f"{f.name}: name must be YYYY-MM-DD-NN-slug.md (lowercase slug)")
            continue
        try:
            fm, body = frontmatter.load(f)
        except frontmatter.FrontMatterError as e:
            errs.append(f"{f.name}: {e}")
            continue
        for k in REQUIRED:
            if k not in fm:
                errs.append(f"{f.name}: missing '{k}'")
        expected_id = f"{m.group(1)}-{m.group(2)}"
        if fm.get("id") != expected_id:
            errs.append(f"{f.name}: id must be {expected_id}")
        if str(fm.get("date")) != m.group(1):
            errs.append(f"{f.name}: date must be {m.group(1)}")
        if fm.get("status") not in STATUSES:
            errs.append(f"{f.name}: status must be one of {sorted(STATUSES)}")
        if fm.get("target") not in TARGETS:
            errs.append(f"{f.name}: target must be one of {sorted(TARGETS)}")
        if not isinstance(fm.get("version"), int) or fm.get("version", 0) < 1:
            errs.append(f"{f.name}: version must be an integer >= 1")
        if not isinstance(fm.get("tickets"), list):
            errs.append(f"{f.name}: tickets must be a list (may be empty)")
        if "## Stop conditions" not in body and fm.get("target") != "human":
            errs.append(f"{f.name}: a prompt for an agent must have a '## Stop conditions' section")
        if "## Report" not in body and fm.get("target") != "human":
            errs.append(f"{f.name}: a prompt for an agent must have a '## Report' section")
        pid = fm.get("id", f.name)
        if pid in ids:
            errs.append(f"{f.name}: duplicate id {pid}")
        ids[pid] = fm
        old = committed(root, f"prompts/{f.name}")
        if old is not None:
            try:
                old_fm, _ = frontmatter.split(old)
            except frontmatter.FrontMatterError:
                old_fm = {}
            new = f.read_text(encoding="utf-8-sig")  # read_text already turns CRLF into LF
            if old_fm.get("status") in FROZEN and STATUS_LINE.sub("", old) != STATUS_LINE.sub("", new):
                errs.append(f"{f.name}: was '{old_fm['status']}' at HEAD, only its status may change; "
                            "write a new prompt with 'supersedes'")
    for pid, fm in ids.items():
        sup = fm.get("supersedes")
        if sup:
            if sup not in ids:
                errs.append(f"{pid}: supersedes unknown prompt {sup}")
            elif ids[sup].get("status") != "superseded":
                errs.append(f"{pid}: supersedes {sup}, so {sup} must have status 'superseded'")
    return errs


if __name__ == "__main__":
    root = Path(sys.argv[1]) if len(sys.argv) > 1 else HERE.parent
    problems = lint(root)
    for p in problems:
        print(p)
    print(f"{'FAIL' if problems else 'OK'}: {len(list((root / 'prompts').glob('*.md')))} prompt(s) checked")
    sys.exit(1 if problems else 0)
