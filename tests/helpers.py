import json
import os
import shutil
import stat
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "factory"))

import config  # noqa: E402

os.environ.update({
    "GIT_AUTHOR_NAME": "test", "GIT_AUTHOR_EMAIL": "test@example.invalid",
    "GIT_COMMITTER_NAME": "test", "GIT_COMMITTER_EMAIL": "test@example.invalid",
})

FX = "/opt/scanner-prompts/factory/fx.py"
PY = sys.executable


def policy() -> dict:
    return json.loads((ROOT / "factory" / "policy.json").read_text(encoding="utf-8"))


def sh(repo, *args):
    res = subprocess.run(["git", *args], cwd=repo, capture_output=True, text=True, encoding="utf-8")
    if res.returncode != 0:
        raise RuntimeError(res.stderr)
    return res.stdout


def write(repo, rel, text):
    p = Path(repo) / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    if isinstance(text, bytes):
        p.write_bytes(text)
    else:
        p.write_text(text, encoding="utf-8", newline="\n")


def commit(repo, msg="T-1: change"):
    sh(repo, "add", "-A")
    sh(repo, "commit", "-q", "-m", msg)


BASE_FILES = {
    "src/scanner/output/emit.py": "def emit(x):\n    return x\n",
    "src/scanner/core.py": "def scan():\n    return []\n",
    "tests/output/test_emit.py": "from x import emit\n\ndef test_a():\n    assert emit(1) == 1\n\ndef test_b():\n    assert emit(2) == 2\n",
    "tests/conftest.py": "import pytest\n",
    "regression/cases/cwe-89/c1/expected.json": "[]\n",
    "regression/golden/c1.json": "{}\n",
    "pyproject.toml": "[project]\nname='s'\n",
    "AGENTS.md": (ROOT / "AGENTS.md").read_text(encoding="utf-8"),
}

BODY = ("\n## Acceptance criteria\n"
        "- AC-1: Given x, then y. Test: `tests/output/test_emit.py::test_c`\n")


def ticket(**over) -> dict:
    t = {
        "id": "T-1", "title": "t", "area": "output", "type": "fix", "status": "ready",
        "allowed_paths": ["src/scanner/output/*", "tests/output/*", "regression/cases/cwe-89/c9/*"],
        "forbidden_paths": [], "new_dependencies": [], "unlock": [],
        "max_diff_lines": 300, "attempts_max": 3,
    }
    t.update(over)
    return t


def ticket_md(t: dict, body: str = BODY) -> str:
    lines = ["---"]
    for k, v in t.items():
        if isinstance(v, list):
            lines.append(f"{k}: [{', '.join(v)}]")
        else:
            lines.append(f"{k}: {v}")
    return "\n".join(lines + ["---", body])


def _rm_readonly(func, path, _):
    os.chmod(path, stat.S_IWRITE)
    func(path)


class FactoryCase(unittest.TestCase):
    """Temp scanner repo + local.json + journal, removed after each test."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="fx-test-"))
        self.addCleanup(shutil.rmtree, self.tmp, onerror=_rm_readonly)
        self.repo = self.tmp / "scanner"
        self.repo.mkdir()
        sh(self.repo, "init", "-q", "-b", "main")
        sh(self.repo, "config", "core.autocrlf", "false")
        for rel, text in BASE_FILES.items():
            write(self.repo, rel, text)
        commit(self.repo, "base")
        self.cfg_path = self.tmp / "local.json"
        self.cfg_path.write_text(json.dumps({
            "repo": str(self.repo), "base": "main", "journal": str(self.tmp / "journal"),
            "max_agents": 2, "sandbox": []}), encoding="utf-8")
        os.environ["FX_CONFIG"] = str(self.cfg_path)
        self.addCleanup(os.environ.pop, "FX_CONFIG", None)
        self.cfg = config.load_local()
        self.policy = policy()

    def ticket_file(self, body: str = BODY, **over) -> Path:
        t = ticket(**over)
        p = self.tmp / f"{t['id']}.md"
        p.write_text(ticket_md(t, body), encoding="utf-8")
        return p
