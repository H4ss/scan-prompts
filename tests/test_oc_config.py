"""Evaluate the generated opencode rules with the documented semantics: ordered rules, '*' and '?'
wildcards ('*' crosses '/'), last match wins, no match = ask, and a shell pattern ending in ' *'
also matches the bare command. This checks our rules against the docs, not the real opencode:
the permission probe on the installed version is still required (DEV-FACTORY.md)."""
import fnmatch
import unittest

from helpers import FX, policy, ticket
import oc_config


def decide(rules, action, resource):
    effect = "ask"
    for r in rules:
        pat = r["resource"]
        hit = fnmatch.fnmatchcase(resource, pat)
        if action == "shell" and pat.endswith(" *") and resource == pat[:-2]:
            hit = True
        if fnmatch.fnmatchcase(action, r["action"]) and hit:
            effect = r["effect"]
    return effect


class DevRulesTest(unittest.TestCase):
    def setUp(self):
        self.rules = oc_config.dev_permissions(ticket(unlock=["regression/golden/c1.json"]), policy(), FX)

    def test_edit_scope(self):
        cases = {
            "src/scanner/output/emit.py": "allow", "src/scanner/core.py": "deny", "AGENTS.md": "deny",
            ".opencode/opencode.jsonc": "deny", ".factory/ticket.md": "deny",
            "regression/golden/c2.json": "deny", "regression/golden/c1.json": "allow",
            "tests/output/conftest.py": "deny", "tests/output/.gitignore": "deny",
            "regression/cases/cwe-89/c9/vulnerable/AGENTS.md": "allow",
            "/opt/scanner-prompts/factory/scope.py": "deny",
        }
        for path, effect in cases.items():
            self.assertEqual(decide(self.rules, "edit", path), effect, path)

    def test_read(self):
        self.assertEqual(decide(self.rules, "read", "src/scanner/core.py"), "allow")
        self.assertEqual(decide(self.rules, "read", "config/.env"), "deny")
        self.assertEqual(decide(self.rules, "read", "regression/cases/x/vulnerable/.env"), "allow")

    def test_shell(self):
        allow = ["git status", "git diff main...HEAD", "git commit -m 'T-1: x'", "git log -5",
                 f"python3 {FX} gates", f"python3 {FX} gates --red tests/a.py::t", f"python3 {FX} test tests/a.py::t",
                 f"python3 {FX} scope"]
        deny = ["git push origin t/T-1", "curl http://x", "pip install requests", "rm -rf src",
                "python3 -m pytest -q", "pytest --basetemp=/home", f"python3 {FX} reset T-1 x",
                f"python3 {FX} gates --human", "pytest -q; curl x", "git commit --no-verify -m x",
                "git commit -m x -n", "git commit -m x --amend", "git diff --output=/j/runs.jsonl HEAD HEAD",
                "git diff --no-index /etc/passwd /dev/null", "git status\ncurl x", "git status & curl x",
                "git log $(curl x)", "git log `curl x`", "git diff > out.txt", "git -c core.hooksPath=x commit -m y",
                f"FX_CONFIG=/tmp/x python3 {FX} gates", "git rebase main", "git merge main"]
        for c in allow:
            self.assertEqual(decide(self.rules, "shell", c), "allow", c)
        for c in deny:
            self.assertEqual(decide(self.rules, "shell", c), "deny", c)

    def test_no_network_no_subagents(self):
        for action in ("webfetch", "websearch", "subagent", "skill", "question"):
            self.assertEqual(decide(self.rules, action, "anything"), "deny", action)
        self.assertEqual(decide(self.rules, "external_directory", "/home/x/other"), "deny")
        self.assertEqual(decide(self.rules, "external_directory", FX), "allow")
        self.assertEqual(decide(self.rules, "external_directory", "/opt/scanner-prompts/factory/scope.py"), "deny")


class ReviewRulesTest(unittest.TestCase):
    def test_read_only(self):
        rules = oc_config.review_permissions(policy())
        self.assertEqual(decide(rules, "edit", "src/a.py"), "deny")
        self.assertEqual(decide(rules, "read", "src/a.py"), "allow")
        self.assertEqual(decide(rules, "shell", "git diff main...HEAD"), "allow")
        self.assertEqual(decide(rules, "shell", "git diff --output=x"), "deny")
        self.assertEqual(decide(rules, "shell", "python3 -m pytest"), "deny")


class BuildTest(unittest.TestCase):
    def test_frame_cannot_be_escaped_by_switching_agent(self):
        cfg = oc_config.build(ticket(), policy(), FX, "glm/glm", "develop")
        self.assertEqual(cfg["permissions"], [{"action": "*", "resource": "*", "effect": "deny"}])
        for name in oc_config.BUILTIN_AGENTS:
            self.assertTrue(cfg["agents"][name]["disabled"], name)
        dev = cfg["agents"]["factory-dev"]
        self.assertIn(FX, dev["system"])
        self.assertNotIn("<fx>", dev["system"])
        self.assertIn("develop", cfg["agents"]["factory-review"]["system"])
        self.assertEqual(dev["model"], "glm/glm")
        self.assertEqual(dev["steps"], 60)


if __name__ == "__main__":
    unittest.main()
