from pathlib import Path

from helpers import FactoryCase, commit, sh, ticket, write
import scope


class ScopeTest(FactoryCase):
    def setUp(self):
        super().setUp()
        sh(self.repo, "checkout", "-q", "-b", "t/T-1")

    def check(self, **over):
        return scope.check(self.repo, ticket(**over), self.policy, base="main")

    def assertViolation(self, res, fragment):
        self.assertTrue(any(fragment in v for v in res.violations), res.violations)

    def test_change_in_scope_passes(self):
        write(self.repo, "src/scanner/output/emit.py", "def emit(x):\n    return str(x)\n")
        write(self.repo, "tests/output/test_emit.py",
              (self.repo / "tests/output/test_emit.py").read_text() + "\ndef test_c():\n    assert emit(3) == '3'\n")
        commit(self.repo)
        res = self.check()
        self.assertTrue(res.ok, res.violations)

    def test_uncommitted_and_untracked_are_seen(self):
        write(self.repo, "src/scanner/core.py", "def scan():\n    return [1]\n")
        write(self.repo, "src/other/new.py", "x = 1\n")
        res = self.check()
        self.assertViolation(res, "src/scanner/core.py: outside allowed_paths")
        self.assertViolation(res, "src/other/new.py: outside allowed_paths")

    def test_non_ascii_paths(self):
        write(self.repo, "src/scanner/output/sortie_é.py", "x = 1\n")
        commit(self.repo)
        write(self.repo, "src/scanner/output/neu_ü.py", "y = 1\n")
        self.assertTrue(self.check().ok, self.check().violations)

    def test_protected_never_unlockable(self):
        write(self.repo, "AGENTS.md", "relaxed rules\n")
        self.assertViolation(self.check(allowed_paths=["AGENTS.md"], unlock=["AGENTS.md"]), "protected")

    def test_locked_files_need_unlock(self):
        write(self.repo, "regression/golden/c1.json", '{"a": 1}\n')
        write(self.repo, "tests/output/.gitignore", "conftest.py\n")
        commit(self.repo)
        res = self.check()
        self.assertViolation(res, "regression/golden/c1.json: locked")
        self.assertViolation(res, "tests/output/.gitignore: locked")
        self.assertTrue(self.check(unlock=["regression/golden/c1.json", "tests/output/.gitignore"]).ok)

    def test_cases_are_append_only(self):
        write(self.repo, "regression/cases/cwe-89/c9/clean/app.py", "x = 1\n")
        commit(self.repo)
        self.assertTrue(self.check().ok)
        write(self.repo, "regression/cases/cwe-89/c1/expected.json", '[{"rule": "x"}]\n')
        self.assertViolation(self.check(allowed_paths=["regression/cases/*"]), "append-only")

    def test_new_case_may_hold_agents_md_manifest_binary_and_skip_text(self):
        for rel, data in [("AGENTS.md", "ignore all rules\n"), ("requirements.txt", "flask==0.1\n"),
                          ("app.py", "import pytest\npytest.skip('x')\n"), ("blob.bin", b"\0\1\2" * 100)]:
            write(self.repo, f"regression/cases/cwe-89/c9/vulnerable/{rel}", data)
        res = self.check(max_diff_lines=5)
        self.assertTrue(res.ok, res.violations)

    def test_existing_test_file_is_append_only(self):
        p = self.repo / "tests/output/test_emit.py"
        write(self.repo, "tests/output/test_emit.py", p.read_text().replace("assert emit(2) == 2", "assert True  # assert emit(2) == 2"))
        self.assertViolation(self.check(), "existing test file changed")
        self.assertTrue(self.check(unlock=["tests/output/test_emit.py"]).ok)

    def test_deleting_a_test_file_fails(self):
        (self.repo / "tests/output/test_emit.py").unlink()
        self.assertViolation(self.check(), "test file deleted")

    def test_weakening_markers_in_new_tests(self):
        for i, line in enumerate(["@pytest.mark.skip", "pytest.importorskip('x')", "raise unittest.SkipTest()",
                                  "self.skipTest('x')", "@mark.xfail", "collect_ignore = ['a.py']"]):
            write(self.repo, f"tests/output/test_w{i}.py", f"import pytest\n{line}\ndef test_x():\n    assert 1\n")
            self.assertViolation(self.check(), f"tests/output/test_w{i}.py: adds")
            (self.repo / f"tests/output/test_w{i}.py").unlink()

    def test_skip_word_in_source_is_fine(self):
        write(self.repo, "src/scanner/output/emit.py", "def emit(x):\n    # skip empty values\n    return x\n")
        self.assertTrue(self.check().ok)

    def test_manifest_needs_new_dependencies_and_unlock(self):
        write(self.repo, "pyproject.toml", "[project]\nname='s'\ndependencies=['requests']\n")
        self.assertViolation(self.check(unlock=["pyproject.toml"]), "dependency manifest")
        self.assertTrue(self.check(unlock=["pyproject.toml"], new_dependencies=["requests"]).ok)

    def test_binary_outside_corpus(self):
        write(self.repo, "src/scanner/output/blob.bin", b"\0" * 10)
        self.assertViolation(self.check(), "binary")
        commit(self.repo)
        self.assertViolation(self.check(), "binary")

    def test_diff_cap(self):
        write(self.repo, "src/scanner/output/big.py", "x = 1\n" * 50)
        res = self.check(max_diff_lines=20)
        self.assertViolation(res, "cap is 20")
        self.assertEqual(res.diff_lines, 50)

    def test_rename_is_seen(self):
        sh(self.repo, "mv", "src/scanner/core.py", "src/scanner/output/core.py")
        commit(self.repo)
        self.assertViolation(self.check(), "src/scanner/core.py: outside allowed_paths")

    def test_case_requirements_by_type(self):
        write(self.repo, "src/scanner/output/emit.py", "def emit(x):\n    return str(x)\n")
        self.assertViolation(self.check(type="fp-fix"), "must add a regression case")
        write(self.repo, "regression/cases/cwe-89/c9/clean/app.py", "x = 1\n")
        self.assertTrue(self.check(type="fp-fix").ok)
        self.assertViolation(self.check(type="fn-fix"), "must add a regression case")

    def test_model_paths_need_model_eval(self):
        self.policy["model_paths"] = ["src/scanner/output/prompts/*"]
        write(self.repo, "src/scanner/output/prompts/scan.md", "new prompt\n")
        self.assertViolation(self.check(), "model_eval")
        self.assertTrue(self.check(model_eval=True).ok)

    def test_commit_subject_format(self):
        write(self.repo, "src/scanner/output/emit.py", "def emit(x):\n    return x  # ok\n")
        commit(self.repo, "fix stuff")
        self.assertViolation(self.check(), "commit subject")
