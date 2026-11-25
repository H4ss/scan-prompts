import shutil
import tempfile
import unittest
from pathlib import Path

from helpers import ROOT, _rm_readonly
import lint_prompts


class LintPromptsTest(unittest.TestCase):
    def test_repository_prompts_are_valid(self):
        self.assertEqual(lint_prompts.lint(ROOT), [])

    def _repo_with(self, name, text):
        d = Path(tempfile.mkdtemp(prefix="fx-prompts-"))
        self.addCleanup(shutil.rmtree, d, onerror=_rm_readonly)
        (d / "prompts").mkdir()
        (d / "prompts" / name).write_text(text, encoding="utf-8")
        return d

    def test_bad_name_and_fields(self):
        d = self._repo_with("Bad Name.md", "---\nid: x\n---\n")
        self.assertTrue(any("name must be" in e for e in lint_prompts.lint(d)))
        d = self._repo_with("2026-11-23-02-x.md", "---\nid: 2026-11-23-01\ndate: 2026-11-23\n---\n")
        errs = lint_prompts.lint(d)
        self.assertTrue(any("id must be 2026-11-23-02" in e for e in errs), errs)
        self.assertTrue(any("missing 'status'" in e for e in errs), errs)

    def test_supersedes_chain(self):
        d = Path(tempfile.mkdtemp(prefix="fx-prompts-"))
        self.addCleanup(shutil.rmtree, d, onerror=_rm_readonly)
        shutil.copytree(ROOT / "prompts", d / "prompts")
        src = (d / "prompts" / "2026-11-23-02-project-inventory.md").read_text(encoding="utf-8")
        newer = src.replace("id: 2026-11-23-02", "id: 2026-11-23-03").replace(
            "supersedes: 2026-11-23-01", "supersedes: 2026-11-23-02")
        (d / "prompts" / "2026-11-23-03-project-inventory.md").write_text(newer, encoding="utf-8")
        errs = lint_prompts.lint(d)
        self.assertTrue(any("must have status 'superseded'" in e for e in errs), errs)

    def test_duplicate_ids(self):
        d = Path(tempfile.mkdtemp(prefix="fx-prompts-"))
        self.addCleanup(shutil.rmtree, d, onerror=_rm_readonly)
        shutil.copytree(ROOT / "prompts", d / "prompts")
        shutil.copy(d / "prompts" / "2026-11-23-02-project-inventory.md", d / "prompts" / "2026-11-23-02-other.md")
        self.assertTrue(any("duplicate id" in e for e in lint_prompts.lint(d)))

    def test_frozen_prompt_only_changes_status(self):
        import subprocess
        d = Path(tempfile.mkdtemp(prefix="fx-prompts-"))
        self.addCleanup(shutil.rmtree, d, onerror=_rm_readonly)
        shutil.copytree(ROOT / "prompts", d / "prompts")
        for args in (["init", "-q"], ["add", "-A"], ["-c", "user.name=t", "-c", "user.email=t@e.invalid", "commit", "-qm", "x"]):
            subprocess.run(["git", *args], cwd=d, check=True)
        f = d / "prompts" / "2026-11-23-02-project-inventory.md"
        f.write_text(f.read_text(encoding="utf-8").replace("status: ready", "status: applied"), encoding="utf-8")
        self.assertEqual(lint_prompts.lint(d), [])
        f.write_text(f.read_text(encoding="utf-8").replace("Read-only.", "Edit freely."), encoding="utf-8")
        self.assertTrue(any("only its status may change" in e for e in lint_prompts.lint(d)))


if __name__ == "__main__":
    unittest.main()
