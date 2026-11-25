#!/usr/bin/env python3
"""fx.py: dev-factory entry point (stdlib only, Python >= 3.7). Settings: factory/local.json.

Human commands:
  fx.py start  <ticket.md>          worktree + branch t/<ID> + frozen contract + opencode config
  fx.py amend  <ID> <ticket.md>     replace the contract of an active ticket (re-scoping)
  fx.py list                        active tickets
  fx.py reset  <ID> <reason>        reset the attempt counter (after sending a ticket back)
  fx.py merge  <ID>                 rebase, gates on a fresh checkout of the rebased commit
  fx.py merge  <ID> --approve       fast-forward the base branch to that exact commit
  fx.py done   <ID>                 remove the merged ticket's worktree and branch
Agent commands (inside the ticket worktree; the ticket comes from the branch name t/<ID>):
  fx.py scope                       touched files vs contract
  fx.py gates                       integrity + scope + configured gates, journaled, attempt cap
  fx.py gates --red <test-id>       prove a ticket test fails before any implementation
  fx.py test <test-id>              run one test while iterating (journaled, not an attempt)
"""
import sys

if sys.version_info < (3, 7):
    sys.exit("fx.py needs Python >= 3.7")

import argparse  # noqa: E402
import json  # noqa: E402
from pathlib import Path  # noqa: E402

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import config  # noqa: E402
import contract  # noqa: E402
import gates  # noqa: E402
import scope  # noqa: E402
import worktrees  # noqa: E402

FX_PATH = str(Path(__file__).resolve()).replace("\\", "/")


def _here_ticket() -> tuple:
    """(worktree, ticket id) from the current directory's branch t/<ID>."""
    top = scope.git_run(".", "rev-parse", "--show-toplevel")
    branch = scope.git_run(".", "symbolic-ref", "--short", "HEAD").stdout.strip()
    if top.returncode != 0 or not branch.startswith(worktrees.PREFIX):
        sys.exit("run agent commands inside a ticket worktree (branch t/<ID>)")
    tid = branch[len(worktrees.PREFIX):]
    if not contract.ID_RE.match(tid):
        sys.exit(f"invalid ticket id in branch {branch!r}")
    return Path(top.stdout.strip()), tid


def main(argv=None) -> int:
    p = argparse.ArgumentParser(prog="fx.py", description=__doc__, allow_abbrev=False,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd")
    sub.required = True
    s = sub.add_parser("start", allow_abbrev=False); s.add_argument("ticket", type=Path)
    s = sub.add_parser("amend", allow_abbrev=False); s.add_argument("id"); s.add_argument("ticket", type=Path)
    sub.add_parser("list", allow_abbrev=False)
    s = sub.add_parser("reset", allow_abbrev=False); s.add_argument("id"); s.add_argument("reason")
    s = sub.add_parser("merge", allow_abbrev=False); s.add_argument("id"); s.add_argument("--approve", action="store_true")
    s = sub.add_parser("done", allow_abbrev=False); s.add_argument("id")
    sub.add_parser("scope", allow_abbrev=False)
    s = sub.add_parser("gates", allow_abbrev=False); s.add_argument("--red", metavar="TEST")
    s = sub.add_parser("test", allow_abbrev=False); s.add_argument("test")

    a = p.parse_args(argv)
    cfg = config.load_local()
    policy = config.load_policy()
    human = a.cmd in ("start", "amend", "list", "reset", "merge", "done")
    if human and not cfg.get("repo"):
        sys.exit("set 'repo' in factory/local.json (copy local.example.json)")

    if a.cmd == "start":
        return worktrees.start(cfg, a.ticket, policy, FX_PATH, HERE.parent / "AGENTS.md")
    if a.cmd == "amend":
        return worktrees.amend(cfg, a.id, a.ticket, policy, FX_PATH)
    if a.cmd == "list":
        for t in worktrees.active(cfg["repo"]):
            try:
                tk, _, _ = contract.load(cfg["journal"], t["id"])
            except SystemExit:
                tk = {}
            print(f"{t['id']:<12} {tk.get('area', '?'):<14} {t['worktree']}  {', '.join(tk.get('allowed_paths', []))}")
        return 0
    if a.cmd == "reset":
        gates.reset(cfg, a.id, a.reason)
        print(f"attempt counter of {a.id} reset")
        return 0
    if a.cmd == "merge":
        return worktrees.merge(cfg, a.id, policy, config.load_gates(cfg), a.approve)
    if a.cmd == "done":
        return worktrees.done(cfg, a.id)

    wt, tid = _here_ticket()
    if a.cmd == "scope":
        ticket, _, state = contract.load(cfg["journal"], tid)
        r = scope.check(wt, ticket, policy, base=state["base"])
        print(json.dumps({"ok": r.ok, "violations": r.violations, "diff_lines": r.diff_lines,
                          "touched": r.touched}, indent=2))
        return 0 if r.ok else 1
    if a.cmd == "gates":
        if a.red:
            return gates.run_red(cfg, policy, config.load_gates(cfg), wt, tid, a.red)
        return gates.run_gates(cfg, policy, config.load_gates(cfg), wt, tid, stage="ticket", fx_path=FX_PATH)
    if a.cmd == "test":
        return gates.run_test(cfg, config.load_gates(cfg), wt, tid, a.test)
    return 2


if __name__ == "__main__":
    sys.exit(main())
