"""One ticket = one worktree = one branch t/<ID>. Cap on active agents, no overlapping scopes,
contract frozen in the journal, two-step merge: gates on a fresh checkout of the rebased commit,
then a fast-forward of exactly that commit."""
from __future__ import annotations

import fnmatch
import re
import shutil
from pathlib import Path

import contract
import frontmatter
import gates
import oc_config
from scope import git, git_run

PREFIX = "t/"


def _ref(tid: str) -> str:
    return f"refs/heads/{PREFIX}{tid}"


def active(repo) -> list:
    """Worktrees whose branch is t/*: [{'worktree', 'branch', 'id'}]."""
    git(repo, "worktree", "prune")
    out, cur = [], {}
    for line in git(repo, "worktree", "list", "--porcelain").splitlines() + [""]:
        if not line:
            br = cur.get("branch", "")
            if br.startswith("refs/heads/" + PREFIX):
                cur["id"] = br[len("refs/heads/" + PREFIX):]
                out.append(cur)
            cur = {}
            continue
        key, _, val = line.partition(" ")
        cur[key] = val
    return out


def _find(repo, tid: str):
    return next((Path(a["worktree"]) for a in active(repo) if a["branch"] == _ref(tid)), None)


def _prefix(glob: str) -> str:
    m = re.search(r"[*?\[]", glob)
    return glob[: m.start()] if m else glob


def overlaps(a: list, b: list) -> list:
    hits = []
    for ga in a or []:
        for gb in b or []:
            pa, pb = _prefix(ga), _prefix(gb)
            if pa.startswith(pb) or pb.startswith(pa):
                hits.append((ga, gb))
    return hits


def _scope_of(t: dict) -> list:
    return (t.get("allowed_paths") or []) + (t.get("unlock") or [])


def _exclude(repo, patterns: list) -> None:
    common = Path(git(repo, "rev-parse", "--git-common-dir").strip())
    if not common.is_absolute():
        common = Path(repo) / common
    exc = common / "info" / "exclude"
    exc.parent.mkdir(parents=True, exist_ok=True)
    existing = exc.read_text(encoding="utf-8").splitlines() if exc.exists() else []
    new = [p for p in patterns if p not in existing]
    if new:
        with open(exc, "a", encoding="utf-8") as fh:
            fh.write("\n".join(new) + "\n")


def _contract_check(text: str, policy: dict) -> tuple:
    ticket, body = frontmatter.split(text)
    return ticket, body, contract.validate(ticket, body, policy)


def start(cfg: dict, ticket_path, policy: dict, fx_path: str, agents_md: Path) -> int:
    repo = Path(cfg["repo"]).resolve()
    base = cfg["base"]
    text = Path(ticket_path).read_text(encoding="utf-8-sig")
    ticket, body, errs = _contract_check(text, policy)
    if errs:
        print("REFUSED: ticket contract invalid:\n  - " + "\n  - ".join(errs))
        return 1
    tid = ticket["id"]
    act = active(repo)
    if any(a["id"] == tid for a in act):
        print(f"REFUSED: {tid} already has a worktree")
        return 1
    if git_run(repo, "rev-parse", "--verify", "--quiet", _ref(tid)).returncode == 0:
        print(f"REFUSED: branch {PREFIX}{tid} already exists; delete it or use another id")
        return 1
    if len(act) >= int(cfg["max_agents"]):
        print(f"REFUSED: {len(act)} active tickets ({', '.join(a['id'] for a in act)}); cap is {cfg['max_agents']}")
        return 1
    for a in act:
        try:
            other, _, _ = contract.load(cfg["journal"], a["id"])
        except SystemExit:
            other = {}
        hits = overlaps(_scope_of(ticket), _scope_of(other))
        if hits:
            print(f"REFUSED: scope overlaps active ticket {a['id']}: " + ", ".join(f"{x} ~ {y}" for x, y in hits))
            return 1
    if git(repo, "ls-files", ".opencode", ".factory").strip():
        print("REFUSED: the scanner repo tracks .opencode/ or .factory/; decide where the generated config goes first")
        return 1
    wt = Path(cfg["wt_root"]) / tid
    if wt.exists():
        print(f"REFUSED: {wt} already exists")
        return 1

    wt.parent.mkdir(parents=True, exist_ok=True)
    git(repo, "worktree", "add", "-b", PREFIX + tid, str(wt), base)
    _exclude(repo, [".factory/", ".opencode/"])
    state = contract.store(cfg["journal"], text, {
        "id": tid, "base": base, "repo": str(repo), "worktree": str(wt),
        "base_head": git(repo, "rev-parse", base).strip()})
    (wt / ".factory").mkdir(exist_ok=True)
    (wt / ".factory" / "ticket.md").write_text(text, encoding="utf-8")
    cfg_path = oc_config.write(wt, ticket, policy, fx_path, cfg.get("model"), base)
    gates.append(cfg, tid, {"kind": "start", "worktree": str(wt), "base": base,
                            "base_head": state["base_head"], "contract_sha256": state["contract_sha256"]})
    print(f"STARTED {tid}\n  worktree: {wt}\n  branch:   {PREFIX}{tid} from {base}\n  opencode: {cfg_path}")
    hot = [h for h in policy.get("hot_files", [])
           if any(fnmatch.fnmatchcase(h, g) or fnmatch.fnmatchcase(g, h) for g in _scope_of(ticket))]
    if hot:
        print("  hot files in scope: " + ", ".join(hot))
    repo_agents = repo / "AGENTS.md"
    if not repo_agents.exists() or repo_agents.read_text(encoding="utf-8") != agents_md.read_text(encoding="utf-8"):
        print("  WARNING: the scanner's AGENTS.md differs from scanner-prompts/AGENTS.md (contract drift)")
    if not cfg.get("sandbox"):
        print("  WARNING: no sandbox configured in local.json")
    print(f"  next: cd {wt} && opencode")
    return 0


def amend(cfg: dict, tid: str, ticket_path, policy: dict, fx_path: str) -> int:
    """Human re-scoping of an active ticket: new contract, new worktree copy, new opencode config."""
    wt = _find(cfg["repo"], tid)
    if wt is None:
        print(f"no active worktree for {tid}")
        return 1
    text = Path(ticket_path).read_text(encoding="utf-8-sig")
    ticket, body, errs = _contract_check(text, policy)
    if ticket.get("id") != tid:
        errs.append(f"id {ticket.get('id')!r} is not {tid}")
    if errs:
        print("REFUSED: ticket contract invalid:\n  - " + "\n  - ".join(errs))
        return 1
    _, _, old = contract.load(cfg["journal"], tid)
    state = contract.store(cfg["journal"], text, {k: v for k, v in old.items() if k != "contract_sha256"})
    (wt / ".factory" / "ticket.md").write_text(text, encoding="utf-8")
    oc_config.write(wt, ticket, policy, fx_path, cfg.get("model"), old["base"])
    gates.append(cfg, tid, {"kind": "amend", "by": "human", "contract_sha256": state["contract_sha256"]})
    print(f"AMENDED {tid}; restart the opencode session so it reloads the config")
    return 0


def _main_ready(repo: Path, base: str) -> str:
    cur = git_run(repo, "symbolic-ref", "--short", "HEAD").stdout.strip()
    if cur != base:
        return f"the main checkout is on {cur or 'a detached HEAD'!r}, not {base!r}"
    if git(repo, "status", "--porcelain", "--untracked-files=no").strip():
        return "the main checkout has uncommitted changes"
    return ""


def merge(cfg: dict, tid: str, policy: dict, gates_cfg: dict, approve: bool) -> int:
    repo = Path(cfg["repo"]).resolve()
    ticket, body, state = contract.load(cfg["journal"], tid)
    base = state["base"]
    wt = _find(repo, tid)
    if wt is None:
        print(f"no active worktree for {tid}")
        return 1
    why = _main_ready(repo, base)
    if why:
        print(f"REFUSED: {why}")
        return 1
    journal = gates.read_journal(cfg, tid)
    tip = git(repo, "rev-parse", _ref(tid)).strip()

    if approve:
        last = next((r for r in reversed(journal) if r.get("kind") == "merge-gates"), None)
        if not last or last.get("result") != "pass" or last.get("sha") != tip:
            print(f"REFUSED: no passing 'fx.py merge {tid}' run on the current tip {tip[:10]}; run it first")
            return 1
        if git_run(repo, "merge-base", "--is-ancestor", base, tip).returncode != 0:
            print(f"REFUSED: {base} moved since the merge gates; run 'fx.py merge {tid}' again")
            return 1
        git(repo, "merge", "--ff-only", tip)
        gates.append(cfg, tid, {"kind": "merge", "sha": tip, "base": base})
        print(f"MERGED {tid} into {base} at {tip[:10]} (fast-forward). Clean up: fx.py done {tid}")
        return 0

    # step 1: preconditions on the agent's work
    if git(wt, "status", "--porcelain").strip():
        print(f"REFUSED: {wt} has uncommitted changes; the agent commits with '{tid}: ...'")
        return 1
    passes = {r.get("head") for r in journal if r.get("kind") == "gates" and r.get("stage") == "ticket"
              and r.get("result") == "pass" and not r.get("dirty")}
    passes |= {r.get("sha") for r in journal if r.get("kind") == "merge-gates"}
    if tip not in passes:
        print(f"REFUSED: no passing agent gates run on the branch tip {tip[:10]}: the agent is not done")
        return 1
    missing = [t for t in contract.ac_tests(body) if t not in gates.red_ok_tests(cfg, tid)]
    if missing:
        print("REFUSED: no RED-OK record for: " + ", ".join(missing))
        return 1

    # step 2: rebase, then gates on a fresh checkout of exactly that commit
    rb = git_run(wt, "rebase", base)
    if rb.returncode != 0:
        git_run(wt, "rebase", "--abort")
        print(f"STOP: rebase of {PREFIX}{tid} on {base} conflicts; human resolves.\n{rb.stdout}{rb.stderr}")
        return 1
    sha = git(wt, "rev-parse", "HEAD").strip()
    tmp = Path(cfg["wt_root"]) / f".merge-{tid}"
    if tmp.exists():
        git_run(repo, "worktree", "remove", "--force", str(tmp))
        shutil.rmtree(tmp, ignore_errors=True)
    git(repo, "worktree", "add", "--detach", str(tmp), sha)
    try:
        rc = gates.run_gates(cfg, policy, gates_cfg, tmp, tid, stage="merge")
    finally:
        git_run(repo, "worktree", "remove", "--force", str(tmp))  # our own temporary checkout
    gates.append(cfg, tid, {"kind": "merge-gates", "sha": sha, "base": base,
                            "base_head": git(repo, "rev-parse", base).strip(),
                            "result": "pass" if rc == 0 else "fail"})
    if rc != 0:
        print(f"NOT MERGEABLE: gates failed on {sha[:10]} after rebase")
        return 1
    print(f"Gates green on {sha[:10]} after rebase. Review (templates/review-checklist.md), then: fx.py merge {tid} --approve")
    return 0


def done(cfg: dict, tid: str) -> int:
    repo = Path(cfg["repo"]).resolve()
    wt = _find(repo, tid)
    if wt is None:
        print(f"no active worktree for {tid}")
        return 1
    if git(wt, "status", "--porcelain").strip():
        print(f"REFUSED: {wt} has uncommitted changes; nothing removed")
        return 1
    rm = git_run(repo, "worktree", "remove", str(wt))  # excluded generated files go with it
    if rm.returncode != 0:
        print(f"REFUSED: {rm.stderr.strip()}")
        return 1
    br = git_run(repo, "branch", "-d", PREFIX + tid)
    print(f"removed worktree {wt}")
    if br.returncode != 0:
        print(f"branch {PREFIX}{tid} kept (not merged into {cfg['base']}): {br.stderr.strip()}")
    gates.append(cfg, tid, {"kind": "done"})
    return 0
