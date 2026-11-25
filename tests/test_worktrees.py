from helpers import FX, PY, FactoryCase, commit, sh, write
import gates
import worktrees


def ok_cfg():
    return {"red": {"cmd": [PY, "-c", "import sys; sys.exit(1)"]},
            "gates": [{"name": "unit", "cmd": [PY, "-c", "pass"]}]}


class WorktreeTest(FactoryCase):
    def start(self, **over):
        return worktrees.start(self.cfg, self.ticket_file(**over), self.policy, FX, self.repo / "AGENTS.md")

    def wt(self, tid="T-1"):
        return self.tmp / "scanner-wt" / tid

    def agent_done(self, tid="T-1"):
        """Simulate the agent: red test, implementation, passing gates."""
        wt = self.wt(tid)
        write(wt, "tests/output/test_emit.py", (wt / "tests/output/test_emit.py").read_text() + "\ndef test_c():\n    assert 1\n")
        self.assertEqual(gates.run_red(self.cfg, self.policy, ok_cfg(), wt, tid, "tests/output/test_emit.py::test_c"), 0)
        write(wt, "src/scanner/output/emit.py", "def emit(x):\n    return str(x)\n")
        commit(wt, f"{tid}: stringify")
        self.assertEqual(gates.run_gates(self.cfg, self.policy, ok_cfg(), wt, tid, fx_path=FX), 0)

    def test_start_creates_worktree_branch_contract_and_config(self):
        self.assertEqual(self.start(), 0)
        cfg = (self.wt() / ".opencode" / "opencode.jsonc").read_text()
        self.assertIn('"default_agent": "factory-dev"', cfg)
        self.assertIn(FX, cfg)
        self.assertIn("t/T-1", sh(self.repo, "branch"))
        self.assertEqual(sh(self.wt(), "status", "--porcelain"), "")  # generated files are excluded
        self.assertTrue((self.tmp / "journal" / "T-1" / "contract.md").exists())

    def test_refuses_invalid_ticket(self):
        self.assertEqual(self.start(status="draft"), 1)
        self.assertEqual(self.start(id="bad id"), 1)
        self.assertEqual(self.start(allowed_paths=[]), 1)
        self.assertEqual(self.start(allowed_paths=["*.py"]), 1)

    def test_refuses_existing_branch(self):
        sh(self.repo, "branch", "t/T-1")
        self.assertEqual(self.start(), 1)

    def test_cap_on_active_agents(self):
        self.assertEqual(self.start(id="T-1", allowed_paths=["src/a/*"]), 0)
        self.assertEqual(self.start(id="T-2", allowed_paths=["src/b/*"]), 0)
        self.assertEqual(self.start(id="T-3", allowed_paths=["src/c/*"]), 1)

    def test_refuses_overlapping_scope_including_unlock(self):
        self.assertEqual(self.start(id="T-1", allowed_paths=["src/scanner/*"]), 0)
        self.assertEqual(self.start(id="T-2", allowed_paths=["src/scanner/output/emit.py"]), 1)
        self.assertEqual(self.start(id="T-3", allowed_paths=["docs/*"], unlock=["regression/golden/c1.json"]), 0)
        self.cfg["max_agents"] = 3
        self.assertEqual(self.start(id="T-4", allowed_paths=["lib/*"], unlock=["regression/golden/c1.json"]), 1)

    def test_amend_rescopes(self):
        self.assertEqual(self.start(), 0)
        p = self.ticket_file(allowed_paths=["src/scanner/*", "tests/output/*"])
        self.assertEqual(worktrees.amend(self.cfg, "T-1", p, self.policy, FX), 0)
        write(self.wt(), "src/scanner/core.py", "x = 2\n")
        commit(self.wt())
        self.assertEqual(gates.run_gates(self.cfg, self.policy, ok_cfg(), self.wt(), "T-1", fx_path=FX), 0)

    def test_merge_flow(self):
        self.assertEqual(self.start(), 0)
        self.agent_done()
        write(self.repo, "docs/readme.md", "x\n")  # main moves meanwhile
        commit(self.repo, "docs")
        self.assertEqual(worktrees.merge(self.cfg, "T-1", self.policy, ok_cfg(), approve=False), 0)
        self.assertNotIn("stringify", sh(self.repo, "log", "--format=%s", "main"))
        self.assertEqual(worktrees.merge(self.cfg, "T-1", self.policy, ok_cfg(), approve=True), 0)
        self.assertIn("T-1: stringify", sh(self.repo, "log", "--format=%s", "main"))
        self.assertFalse((self.tmp / "scanner-wt" / ".merge-T-1").exists())
        self.assertEqual(worktrees.done(self.cfg, "T-1"), 0)
        self.assertFalse(self.wt().exists())
        self.assertNotIn("t/T-1", sh(self.repo, "branch"))

    def test_merge_refusals(self):
        self.assertEqual(self.start(), 0)
        # agent not done: no passing gates on the tip
        write(self.wt(), "src/scanner/output/emit.py", "def emit(x):\n    return 0\n")
        commit(self.wt())
        self.assertEqual(worktrees.merge(self.cfg, "T-1", self.policy, ok_cfg(), approve=False), 1)
        # approve without a merge-gates pass
        self.assertEqual(worktrees.merge(self.cfg, "T-1", self.policy, ok_cfg(), approve=True), 1)

    def test_merge_refuses_without_red_ok(self):
        self.assertEqual(self.start(), 0)
        write(self.wt(), "src/scanner/output/emit.py", "def emit(x):\n    return str(x)\n")
        commit(self.wt())
        self.assertEqual(gates.run_gates(self.cfg, self.policy, ok_cfg(), self.wt(), "T-1", fx_path=FX), 0)
        self.assertEqual(worktrees.merge(self.cfg, "T-1", self.policy, ok_cfg(), approve=False), 1)

    def test_merge_refuses_when_main_checkout_not_on_base(self):
        self.assertEqual(self.start(), 0)
        self.agent_done()
        sh(self.repo, "checkout", "-q", "-b", "human-wip")
        self.assertEqual(worktrees.merge(self.cfg, "T-1", self.policy, ok_cfg(), approve=False), 1)

    def test_approve_refuses_new_commit_after_merge_gates(self):
        self.assertEqual(self.start(), 0)
        self.agent_done()
        self.assertEqual(worktrees.merge(self.cfg, "T-1", self.policy, ok_cfg(), approve=False), 0)
        write(self.wt(), "src/scanner/output/emit.py", "def emit(x):\n    return 'late'\n")
        commit(self.wt(), "T-1: late change")
        self.assertEqual(worktrees.merge(self.cfg, "T-1", self.policy, ok_cfg(), approve=True), 1)
        self.assertNotIn("late change", sh(self.repo, "log", "--format=%s", "main"))

    def test_merge_gates_run_on_fresh_checkout(self):
        """A gitignored file in the agent's worktree must not influence the merge gates."""
        self.assertEqual(self.start(), 0)
        self.agent_done()
        write(self.wt(), ".factory/marker", "x")  # excluded, invisible to git status
        probe = {"red": ok_cfg()["red"], "gates": [{"name": "probe", "cmd": [
            PY, "-c", "import os, sys; sys.exit(1 if os.path.exists('.factory/marker') else 0)"]}]}
        self.assertEqual(worktrees.merge(self.cfg, "T-1", self.policy, probe, approve=False), 0)

    def test_done_refuses_dirty(self):
        self.assertEqual(self.start(), 0)
        write(self.wt(), "src/scanner/output/emit.py", "changed\n")
        self.assertEqual(worktrees.done(self.cfg, "T-1"), 1)
        self.assertTrue(self.wt().exists())

    def test_overlap_prefixes(self):
        self.assertTrue(worktrees.overlaps(["src/*"], ["src/x/y.py"]))
        self.assertFalse(worktrees.overlaps(["src/a/*"], ["src/b/*"]))
