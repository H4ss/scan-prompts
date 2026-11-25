import unittest

from helpers import ROOT, policy
import contract
import frontmatter


class FrontMatterTest(unittest.TestCase):
    def test_ticket_template_parses_and_is_a_valid_contract_once_ready(self):
        fm, body = frontmatter.load(ROOT / "templates" / "ticket.md")
        self.assertEqual(fm["id"], "T-000")
        self.assertEqual(fm["area"], "output")  # trailing comment stripped
        self.assertEqual(fm["new_dependencies"], [])
        self.assertIs(fm["model_eval"], False)
        self.assertEqual(fm["max_diff_lines"], 300)
        fm["status"] = "ready"
        self.assertEqual(contract.validate(fm, body, policy()), [])

    def test_inline_list_quotes_hash_and_leading_zero(self):
        fm, _ = frontmatter.split('---\na: ["x, y", z]\nb: "0.1"\ntitle: Fix #123\nid: 0042\nn: 12  # c\n---\nbody')
        self.assertEqual(fm["a"], ["x, y", "z"])
        self.assertEqual(fm["b"], "0.1")
        self.assertEqual(fm["title"], "Fix #123")
        self.assertEqual(fm["id"], "0042")
        self.assertEqual(fm["n"], 12)

    def test_bom_is_accepted(self):
        fm, _ = frontmatter.split("\ufeff---\na: 1\n---\n")
        self.assertEqual(fm["a"], 1)

    def test_rejects_malformed(self):
        for bad in ("no header", "---\na: 1\n", "---\n  nested: 1\n---\n", "---\na: 1\na: 2\n---\n",
                    "---\n- orphan\n---\n", '---\na: "open\n---\n'):
            with self.assertRaises(frontmatter.FrontMatterError, msg=bad):
                frontmatter.split(bad)


class ContractTest(unittest.TestCase):
    def base(self, **over):
        t = {"id": "T-1", "title": "t", "area": "a", "type": "fix", "status": "ready",
             "allowed_paths": ["src/a/*"]}
        t.update(over)
        return t

    BODY = "- AC-1: x. Test: `tests/a.py::test_x`\n"

    def errs(self, body=BODY, **over):
        return contract.validate(self.base(**over), body, policy())

    def test_valid(self):
        self.assertEqual(self.errs(), [])

    def test_globs_must_be_anchored_relative(self):
        for g in ("*.py", "/etc/*", "~/x", "src/../x", "C:/x", "src\\x"):
            self.assertTrue(self.errs(allowed_paths=[g]), g)

    def test_unlock_exact_paths_only(self):
        self.assertEqual(self.errs(unlock=["regression/golden/c1.json"]), [])
        self.assertTrue(self.errs(unlock=["regression/golden/*"]))

    def test_every_criterion_needs_a_test(self):
        self.assertTrue(self.errs(body="- AC-1: x\n"))
        self.assertTrue(self.errs(body="nothing\n"))
        self.assertTrue(self.errs(body="- AC-1: x. Test: `--basetemp=/x`\n"))

    def test_types_and_ids(self):
        self.assertTrue(self.errs(type="hack"))
        self.assertTrue(self.errs(id="../x"))
        self.assertTrue(self.errs(id=42))
        self.assertTrue(self.errs(max_diff_lines="9"))
        self.assertTrue(self.errs(status="draft"))


if __name__ == "__main__":
    unittest.main()
