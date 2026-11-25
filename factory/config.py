"""Machine-local settings and policy.

factory/local.json (gitignored, copy of local.example.json) holds everything machine-specific:
scanner checkout, base branch, worktree root, journal dir, agent cap, model, gates file, sandbox.
FX_CONFIG may point to another file (tests). Agents cannot set it: their shell allowlist starts
with 'python3 <fx>', so no environment prefix is possible.

policy.json (tracked, generic) + policy.local.json (gitignored, company-specific globs):
keys of the local file replace the tracked ones.
"""
from __future__ import annotations

import json
import os
from pathlib import Path

HERE = Path(__file__).resolve().parent

DEFAULTS = {
    "repo": None,
    "base": "main",
    "wt_root": None,
    "journal": None,
    "max_agents": 2,
    "model": None,
    "gates": "gates.json",
    "sandbox": [],
}


def _read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def load_local() -> dict:
    path = Path(os.environ.get("FX_CONFIG") or HERE / "local.json")
    cfg = dict(DEFAULTS)
    if path.exists():
        cfg.update(_read_json(path))
    if cfg["journal"] is None:
        cfg["journal"] = str(Path.home() / ".local" / "state" / "scanner-factory" / "journal")
    if cfg["repo"] and cfg["wt_root"] is None:
        repo = Path(cfg["repo"])
        cfg["wt_root"] = str(repo.parent / f"{repo.name}-wt")
    return cfg


def load_policy() -> dict:
    policy = _read_json(HERE / "policy.json")
    local = HERE / "policy.local.json"
    if local.exists():
        policy.update(_read_json(local))
    return policy


def load_gates(cfg: dict) -> dict:
    path = Path(cfg["gates"])
    if not path.is_absolute():
        path = HERE / path
    if not path.exists():
        raise SystemExit(f"no gates config at {path}: copy factory/gates.example.json and fill it")
    return _read_json(path)
