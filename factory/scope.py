"""Scope gate: what the branch changed must match the ticket contract.

All checks are deterministic and run against the merge-base with the ticket's base branch,
on committed + uncommitted + untracked changes:
  - touched paths inside allowed_paths; never-protected paths untouched
  - unlockable paths (goldens, test config, .gitignore, pyproject...) only if listed in `unlock`
  - append-only paths (regression cases): additions only; protected/manifest/binary checks skipped
  - test files that exist at the merge-base are append-only (no removed or changed line) unless unlocked
  - no skip/xfail/collection tricks added in test files or conftest
  - dependency manifests unchanged unless new_dependencies is set
  - model paths touched only with model_eval: true
  - fp-fix adds a clean case, fn-fix adds a vulnerable case
  - no binary file outside append-only paths
  - diff size <= max_diff_lines (append-only paths not counted)
  - every commit subject starts with '<ID>: '
"""
from __future__ import annotations

import fnmatch
import re
import subprocess
from dataclasses import dataclass, field
from pathlib import Path

CONFTEST = ["conftest.py", "*/conftest.py"]


def git_run(repo, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(["git", "-c", "core.quotePath=false", *args], cwd=repo, capture_output=True,
                          text=True, encoding="utf-8", errors="replace")


def git(repo, *args: str, check: bool = True) -> str:
    res = git_run(repo, *args)
    if check and res.returncode != 0:
        raise RuntimeError(f"git {' '.join(args)} failed: {res.stderr.strip()}")
    return res.stdout


def matches(path: str, globs) -> bool:
    return any(fnmatch.fnmatchcase(path, g) for g in globs or [])


@dataclass
class Change:
    status: str            # A, M, D, R
    path: str
    old_path: str = ""
    tracked: bool = True   # False = untracked file


@dataclass
class ScopeResult:
    violations: list = field(default_factory=list)
    touched: list = field(default_factory=list)
    diff_lines: int = 0
    base: str = ""

    @property
    def ok(self) -> bool:
        return not self.violations


def merge_base(repo, base: str) -> str:
    return git(repo, "merge-base", base, "HEAD").strip()


def changes(repo, mb: str) -> list:
    out = []
    tokens = git(repo, "diff", "-z", "--name-status", "-M", mb).split("\0")
    i = 0
    while i < len(tokens) and tokens[i]:
        code = tokens[i][0]
        if code in "RC":
            out.append(Change("R" if code == "R" else "A", tokens[i + 2], tokens[i + 1]))
            i += 3
        else:
            out.append(Change({"T": "M"}.get(code, code), tokens[i + 1]))
            i += 2
    for path in git(repo, "ls-files", "-z", "--others", "--exclude-standard").split("\0"):
        if path:
            out.append(Change("A", path, tracked=False))
    return out


def numstat(repo, mb: str) -> dict:
    """path -> lines changed, or -1 for binary."""
    sizes = {}
    tokens = git(repo, "diff", "-z", "--numstat", "-M", mb).split("\0")
    i = 0
    while i < len(tokens) and tokens[i]:
        added, deleted, path = tokens[i].split("\t", 2)
        if path == "":           # rename: old and new paths follow
            path = tokens[i + 2]
            i += 3
        else:
            i += 1
        sizes[path] = -1 if added == "-" else int(added) + int(deleted)
    return sizes


def _read_bytes(repo, rel: str) -> bytes:
    try:
        return (Path(repo) / rel).read_bytes()
    except OSError:
        return b""


def _is_binary(data: bytes) -> bool:
    return b"\0" in data[:8192]


def _diff_lines(repo, mb: str, path: str, sign: str) -> list:
    diff = git(repo, "diff", "-U0", mb, "--", path)
    return [l[1:] for l in diff.splitlines() if l.startswith(sign) and not l.startswith(sign * 3)]


def check(repo, ticket: dict, policy: dict, base: str) -> ScopeResult:
    repo = Path(repo)
    res = ScopeResult()
    mb = merge_base(repo, base)
    res.base = mb
    tid = str(ticket.get("id") or "")
    allowed = ticket.get("allowed_paths") or []
    forbidden = ticket.get("forbidden_paths") or []
    unlock = set(ticket.get("unlock") or [])
    protected = policy.get("protected", [])
    unlockable = policy.get("unlockable", [])
    append_only = policy.get("append_only", [])
    test_globs = policy.get("tests", {}).get("globs", [])
    weakening = policy.get("tests", {}).get("weakening_patterns", [])
    manifests = policy.get("dependency_manifests", [])
    model_paths = policy.get("model_paths", [])
    v = res.violations
    if not allowed:
        v.append("ticket allowed_paths is empty")

    chs = changes(repo, mb)
    stats = numstat(repo, mb)
    total = 0
    added_paths = []
    for ch in chs:
        for p in [ch.path] + ([ch.old_path] if ch.old_path else []):
            res.touched.append(p)
            in_corpus = matches(p, append_only)
            if in_corpus:
                if ch.status != "A":
                    v.append(f"{p}: append-only path ({ch.status}); existing regression cases are immutable")
                if not matches(p, allowed):
                    v.append(f"{p}: outside allowed_paths")
                continue
            if matches(p, protected):
                v.append(f"{p}: protected path, never changed by an agent")
                continue
            if matches(p, unlockable):
                if p not in unlock:
                    v.append(f"{p}: locked file; the ticket must list it in unlock")
            elif not matches(p, allowed):
                v.append(f"{p}: outside allowed_paths")
            if matches(p, forbidden):
                v.append(f"{p}: forbidden by the ticket")
            if matches(p, manifests) and not ticket.get("new_dependencies"):
                v.append(f"{p}: dependency manifest changed but new_dependencies is empty")
            if matches(p, model_paths) and not ticket.get("model_eval"):
                v.append(f"{p}: model/prompt path changed; the ticket must set model_eval: true")

        if ch.status == "A" and not ch.old_path:
            added_paths.append(ch.path)
        in_corpus = matches(ch.path, append_only)
        is_test = matches(ch.path, test_globs) or matches(ch.path, CONFTEST)
        was_test = ch.old_path and matches(ch.old_path, test_globs)

        if (is_test or was_test) and ch.status == "D":
            v.append(f"{ch.path}: test file deleted")
        if is_test and ch.status in ("M", "R") and ch.path not in unlock:
            removed = _diff_lines(repo, mb, ch.path, "-") if ch.status == "M" else ["(renamed)"]
            if removed:
                v.append(f"{ch.path}: existing test file changed ({len(removed)} line(s) removed or edited); "
                         "tests are append-only unless the file is in unlock")
        if is_test and ch.status != "D" and not in_corpus:
            if ch.tracked:
                added = _diff_lines(repo, mb, ch.path, "+")
            else:
                added = _read_bytes(repo, ch.path).decode("utf-8", "replace").splitlines()
            for line in added:
                hit = next((pat for pat in weakening if re.search(pat, line)), None)
                if hit:
                    v.append(f"{ch.path}: adds a skip/xfail/collection marker ({hit})")
                    break

        # size and binaries
        if ch.status == "D":
            n = stats.get(ch.path, 0)
        elif ch.tracked:
            n = stats.get(ch.path, 0)
        else:
            data = _read_bytes(repo, ch.path)
            n = -1 if _is_binary(data) else len(data.decode("utf-8", "replace").splitlines())
        if n == -1:
            if not in_corpus:
                v.append(f"{ch.path}: binary file outside the regression corpus")
        elif not in_corpus:
            total += n

    res.diff_lines = total
    cap = int(ticket.get("max_diff_lines") or policy.get("defaults", {}).get("max_diff_lines", 400))
    if total > cap:
        v.append(f"diff is {total} lines, cap is {cap}")

    required = policy.get("case_requirements", {}).get(ticket.get("type"))
    if required and not any(fnmatch.fnmatchcase(p, required) for p in added_paths):
        v.append(f"ticket type {ticket.get('type')} must add a regression case matching {required}")

    subj_re = re.compile(policy.get("commit_subject", "^{id}: \\S").replace("{id}", re.escape(tid)))
    for subject in git(repo, "log", "--format=%s", f"{mb}..HEAD").splitlines():
        if not subj_re.search(subject):
            v.append(f"commit subject does not start with '{tid}: ': {subject!r}")

    res.violations = list(dict.fromkeys(v))
    res.touched = sorted(set(res.touched))
    return res
