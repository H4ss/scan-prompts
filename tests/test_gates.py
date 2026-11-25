from helpers import FX, PY, BODY, FactoryCase, commit, write
import gates
import worktrees


def gcfg(gate_code=0, red_code=1, red_fail_codes=None):
    red = {"cmd": [PY, "-c", f"import sys; print('{{test}}'); sys.exit({red_code})"]}
    if red_fail_codes is not None:
        red["fail_codes"] = red_fail_codes
    return {
        "red": red,
        "gates": [
            {"name": "unit", "cmd": [PY, "-c", f"import sys; sys.exit({gate_code})"]},
            {"name": "slow", "stage": "merge", "cmd": [PY, "-c", "import sys; sys.exit(1)"]},
            {"name": "model", "when": "model_eval", "cmd": [PY, "-c", "import sys; sys.exit(1)"]},
        ],
    }


class GatesTest(FactoryCase):
    def setUp(self):
        super().setUp()
        self.assertEqual(worktrees.start(self.cfg, self.ticket_file(), self.policy, FX, self.repo / "AGENTS.md"), 0)
        self.wt = self.tmp / "scanner-wt" / "T-1"

    def implement(self):
        write(self.wt, "src/scanner/output/emit.py", "def emit(x):\n    return str(x)\n")
        commit(self.wt)

    def run_gates(self, g, **kw):
        return gates.run_gates(self.cfg, self.policy, g, self.wt, "T-1", fx_path=FX, **kw)

    def test_pass_is_journaled(self):
        self.implement()
        self.assertEqual(self.run_gates(gcfg(0)), 0)
        rec = gates.read_journal(self.cfg, "T-1")[-1]
        self.assertEqual(rec["result"], "pass")
        self.assertEqual([g["gate"] for g in rec["gates"]], ["integrity", "scope", "unit"])
        self.assertEqual(len(rec["head"]), 40)
        self.assertFalse(rec["dirty"])

    def test_stop_after_attempts_max_and_human_reset(self):
        self.implement()
        self.assertEqual(self.run_gates(gcfg(1)), 1)
        self.assertEqual(self.run_gates(gcfg(1)), 1)
        self.assertEqual(self.run_gates(gcfg(1)), 3)
        self.assertEqual(self.run_gates(gcfg(0)), 3)  # refuses even if it would pass
        gates.reset(self.cfg, "T-1", "sent back after review")
        self.assertEqual(self.run_gates(gcfg(0)), 0)

    def test_merge_stage_failures_do_not_use_agent_attempts(self):
        self.implement()
        for _ in range(4):
            gates.run_gates(self.cfg, self.policy, gcfg(1), self.wt, "T-1", stage="merge")
        self.assertEqual(gates.failed_attempts(self.cfg, "T-1"), 0)

    def test_tampered_ticket_copy_or_opencode_config_fails(self):
        self.implement()
        p = self.wt / ".factory" / "ticket.md"
        p.write_text(p.read_text().replace("src/scanner/output/*", "src/*"), encoding="utf-8")
        self.assertEqual(self.run_gates(gcfg(0)), 1)
        self.assertIn("integrity", str(gates.read_journal(self.cfg, "T-1")[-1]["gates"][0]))

    def test_scope_uses_journal_contract_not_worktree_copy(self):
        write(self.wt, "src/scanner/core.py", "x = 2\n")
        commit(self.wt)
        p = self.wt / ".factory" / "ticket.md"
        p.write_text(p.read_text().replace("src/scanner/output/*", "src/*"), encoding="utf-8")
        self.run_gates(gcfg(0), keep_going=True)
        rec = gates.read_journal(self.cfg, "T-1")[-1]
        scope_rec = next(g for g in rec["gates"] if g["gate"] == "scope")
        self.assertTrue(any("src/scanner/core.py" in v for v in scope_rec["violations"]))

    def test_red_ok_only_for_ticket_tests_with_failure_code(self):
        test = "tests/output/test_emit.py::test_c"
        self.assertEqual(gates.run_red(self.cfg, self.policy, gcfg(red_code=2), self.wt, "T-1", test), 1)
        self.assertEqual(gates.run_red(self.cfg, self.policy, gcfg(red_code=0), self.wt, "T-1", test), 1)
        self.assertEqual(gates.run_red(self.cfg, self.policy, gcfg(red_code=1), self.wt, "T-1", "tests/other.py::t"), 1)
        self.assertEqual(gates.run_red(self.cfg, self.policy, gcfg(red_code=1), self.wt, "T-1", test), 0)
        self.assertEqual(gates.red_ok_tests(self.cfg, "T-1"), {test})

    def test_red_refused_once_implementation_changed(self):
        write(self.wt, "tests/output/test_emit.py",
              (self.wt / "tests/output/test_emit.py").read_text() + "\ndef test_c():\n    assert 0\n")
        self.implement()
        rc = gates.run_red(self.cfg, self.policy, gcfg(red_code=1), self.wt, "T-1", "tests/output/test_emit.py::test_c")
        self.assertEqual(rc, 1)

    def test_timeout_is_recorded(self):
        self.implement()
        g = {"gates": [{"name": "hang", "timeout": 1, "cmd": [PY, "-c", "import time; time.sleep(30)"]}]}
        self.assertEqual(self.run_gates(g), 1)
        rec = gates.read_journal(self.cfg, "T-1")[-1]
        self.assertEqual(rec["gates"][-1]["exit"], 124)

    def test_sandbox_prefix_is_applied(self):
        self.cfg["sandbox"] = [PY, "-c", "import sys; sys.exit(7)", "{worktree}"]
        self.implement()
        self.assertEqual(self.run_gates(gcfg(0)), 1)
        last = gates.read_journal(self.cfg, "T-1")[-1]["gates"][-1]
        self.assertEqual(last["exit"], 7)
        self.assertIn(str(self.wt), last["argv"])
