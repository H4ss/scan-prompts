"""Gate runner + journal.

The journal is the record of what really ran: <journal>/<ID>/runs.jsonl (one JSON line per run)
plus a .log per command. It lives outside the worktree; with a sandbox configured, test commands
cannot write to it. The contract used is the journal copy, never the worktree copy.
"""
from __future__ import annotations

import json
import os
import signal
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path

import contract
import oc_config
import scope

TAIL_LINES = 40


# ---------- journal ----------

def _dir(cfg: dict, tid: str) -> Path:
    return contract.ticket_dir(cfg["journal"], tid)


def read_journal(cfg: dict, tid: str) -> list:
    f = _dir(cfg, tid) / "runs.jsonl"
    if not f.exists():
        return []
    out = []
    for line in f.read_text(encoding="utf-8").splitlines():
        if line.strip():
            out.append(json.loads(line))
    return out


def append(cfg: dict, tid: str, record: dict) -> None:
    record = dict({"ts": now()}, **record)
    with open(_dir(cfg, tid) / "runs.jsonl", "a", encoding="utf-8") as fh:
        fh.write(json.dumps(record, ensure_ascii=False) + "\n")


def now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H%M%S.%fZ")


def failed_attempts(cfg: dict, tid: str) -> int:
    n = 0
    for rec in read_journal(cfg, tid):
        if rec.get("kind") == "reset":
            n = 0
        elif rec.get("kind") == "gates" and rec.get("stage") == "ticket" and rec.get("result") == "fail":
            n += 1
    return n


def reset(cfg: dict, tid: str, reason: str) -> None:
    append(cfg, tid, {"kind": "reset", "by": "human", "reason": reason})


# ---------- command execution ----------

def _argv(cmd, worktree: Path, cfg: dict, subst: dict, use_sandbox: bool = True) -> list:
    argv = list(cmd) if isinstance(cmd, list) else cmd.split()
    for key, val in subst.items():
        argv = [a.replace("{" + key + "}", val) for a in argv]
    sandbox = [a.replace("{worktree}", str(worktree)) for a in (cfg.get("sandbox") or [] if use_sandbox else [])]
    return sandbox + argv


def run_cmd(cfg: dict, tid: str, name: str, cmd, worktree: Path, timeout: int, subst: dict,
            use_sandbox: bool = True) -> dict:
    argv = _argv(cmd, worktree, cfg, subst, use_sandbox)
    start = time.monotonic()
    posix = os.name == "posix"
    try:
        proc = subprocess.Popen(argv, cwd=worktree, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                start_new_session=posix)
        try:
            out, _ = proc.communicate(timeout=timeout)
            code = proc.returncode
        except subprocess.TimeoutExpired:
            if posix:
                os.killpg(proc.pid, signal.SIGKILL)  # the whole group: xdist workers, model calls
            else:
                proc.kill()
            out, _ = proc.communicate()
            code = 124
            out = (out or b"") + f"\nTIMEOUT after {timeout}s\n".encode()
    except FileNotFoundError as exc:
        code, out = 127, f"command not found: {exc}".encode()
    output = (out or b"").decode("utf-8", "replace")
    log = _dir(cfg, tid) / f"{now()}-{name}.log"
    log.write_text(output, encoding="utf-8")
    return {"gate": name, "argv": argv, "exit": code, "seconds": round(time.monotonic() - start, 2),
            "sandbox": bool(cfg.get("sandbox")) and use_sandbox, "log": str(log), "tail": output.splitlines()[-TAIL_LINES:]}


def _head(worktree: Path) -> tuple:
    return (scope.git(worktree, "rev-parse", "HEAD").strip(),
            bool(scope.git(worktree, "status", "--porcelain").strip()))


# ---------- integrity of the agent's view ----------

def integrity(cfg: dict, policy: dict, worktree: Path, tid: str, fx_path: str) -> list:
    """The worktree copies of the contract and the opencode config must match what fx generated."""
    ticket, _, state = contract.load(cfg["journal"], tid)
    problems = []
    copy = Path(worktree) / ".factory" / "ticket.md"
    if not copy.exists() or contract.sha256(copy.read_text(encoding="utf-8")) != state["contract_sha256"]:
        problems.append(".factory/ticket.md differs from the contract stored at start (only 'fx.py amend' changes it)")
    oc = Path(worktree) / ".opencode" / "opencode.jsonc"
    expected = oc_config.render(ticket, policy, fx_path, cfg.get("model"), state["base"])
    if not oc.exists() or oc.read_text(encoding="utf-8") != expected:
        problems.append(".opencode/opencode.jsonc differs from the generated config")
    return problems


# ---------- gates ----------

def run_gates(cfg: dict, policy: dict, gates_cfg: dict, worktree: Path, tid: str, stage: str = "ticket",
              fx_path: str = "", keep_going: bool = False) -> int:
    """0 = all gates pass, 1 = failure, 3 = STOP (attempt cap reached, ticket stage only)."""
    worktree = Path(worktree)
    ticket, _, state = contract.load(cfg["journal"], tid)
    cap = int(ticket.get("attempts_max") or policy.get("defaults", {}).get("attempts_max", 3))
    if stage == "ticket" and failed_attempts(cfg, tid) >= cap:
        print(f"STOP: {cap} failed gate runs for {tid}. Write the BLOCKED report and hand back to the human.")
        return 3
    sha, dirty = _head(worktree)
    results, ok = [], True
    if not cfg.get("sandbox"):
        print("WARNING: no sandbox configured; test commands run with the user's full rights")

    if stage == "ticket":
        problems = integrity(cfg, policy, worktree, tid, fx_path)
        results.append({"gate": "integrity", "exit": 1 if problems else 0, "violations": problems})
        print(f"[{'FAIL' if problems else 'PASS'}] integrity")
        for p in problems:
            print(f"    - {p}")
        ok = not problems

    if ok or keep_going:
        sc = scope.check(worktree, ticket, policy, base=state["base"])
        results.append({"gate": "scope", "exit": 0 if sc.ok else 1, "violations": sc.violations,
                        "diff_lines": sc.diff_lines, "touched": sc.touched})
        print(f"[{'PASS' if sc.ok else 'FAIL'}] scope ({sc.diff_lines} diff lines)")
        for v in sc.violations:
            print(f"    - {v}")
        ok = ok and sc.ok

    if ok or keep_going:
        for g in gates_cfg.get("gates", []):
            if g.get("stage", "ticket") == "merge" and stage != "merge":
                continue
            if g.get("when") and not ticket.get(g["when"]):
                continue
            # "sandbox": false is allowed only on merge-stage gates (e.g. the live-model eval needs the GLM endpoint)
            use_sb = not (g.get("sandbox") is False and g.get("stage") == "merge")
            r = run_cmd(cfg, tid, g["name"], g["cmd"], worktree, int(g.get("timeout", 600)), {}, use_sb)
            results.append(r)
            passed = r["exit"] == 0
            print(f"[{'PASS' if passed else 'FAIL'}] {g['name']} (exit {r['exit']}, {r['seconds']}s) log: {r['log']}")
            if not passed:
                print("\n".join("    " + l for l in r["tail"][-15:]))
                ok = False
                if not keep_going:
                    break

    append(cfg, tid, {"kind": "gates", "stage": stage, "head": sha, "dirty": dirty,
                      "result": "pass" if ok else "fail", "gates": results})
    if not ok and stage == "ticket":
        left = cap - failed_attempts(cfg, tid)
        print(f"Attempts left for {tid}: {max(left, 0)}/{cap}")
        if left <= 0:
            print("STOP: attempt cap reached. Write the BLOCKED report and hand back to the human.")
            return 3
    return 0 if ok else 1


def _valid_test_id(test: str) -> bool:
    return bool(contract.TEST_ID_RE.match(test)) and not test.startswith("-")


def run_red(cfg: dict, policy: dict, gates_cfg: dict, worktree: Path, tid: str, test: str) -> int:
    """A ticket test must FAIL (exit code in red.fail_codes, default [1]) before any implementation."""
    worktree = Path(worktree)
    ticket, body, state = contract.load(cfg["journal"], tid)
    if test not in contract.ac_tests(body):
        print(f"[RED-INVALID] {test!r} is not one of the ticket's tests: {contract.ac_tests(body)}")
        return 1
    if not _valid_test_id(test):
        print(f"[RED-INVALID] {test!r}: invalid test id")
        return 1
    red = gates_cfg.get("red")
    if not red:
        print("gates config has no 'red' command")
        return 2
    mb = scope.merge_base(worktree, state["base"])
    allowed_now = policy.get("tests", {}).get("globs", []) + scope.CONFTEST + policy.get("append_only", [])
    impl = [c.path for c in scope.changes(worktree, mb) if not scope.matches(c.path, allowed_now)]
    sha, dirty = _head(worktree)
    if impl:
        print("[RED-INVALID] non-test files already changed, write and check all tests first: " + ", ".join(impl))
        append(cfg, tid, {"kind": "red", "test": test, "head": sha, "result": "red-invalid", "reason": "impl-changed"})
        return 1
    r = run_cmd(cfg, tid, "red", red["cmd"], worktree, int(red.get("timeout", 300)), {"test": test})
    fail_codes = red.get("fail_codes", [1])
    good = r["exit"] in fail_codes
    append(cfg, tid, {"kind": "red", "test": test, "head": sha, "dirty": dirty,
                      "result": "red-ok" if good else "red-invalid", "run": r})
    if good:
        print(f"[RED-OK] {test} fails before the change (exit {r['exit']}). log: {r['log']}")
        return 0
    if r["exit"] == 0:
        print(f"[RED-INVALID] {test} already passes: it does not test the change.")
    else:
        print(f"[RED-INVALID] {test}: exit {r['exit']} is not a test failure {fail_codes} "
              f"(collection error, unknown id, no test run?). log: {r['log']}")
    return 1


def run_test(cfg: dict, gates_cfg: dict, worktree: Path, tid: str, test: str) -> int:
    """Run one test while iterating. Journaled, not counted as an attempt."""
    if not _valid_test_id(test):
        print(f"invalid test id {test!r}")
        return 2
    t = gates_cfg.get("test") or gates_cfg.get("red")
    r = run_cmd(cfg, tid, "test", t["cmd"], Path(worktree), int(t.get("timeout", 300)), {"test": test})
    append(cfg, tid, {"kind": "test", "test": test, "exit": r["exit"], "log": r["log"]})
    print("\n".join(r["tail"]))
    print(f"exit {r['exit']} log: {r['log']}")
    return 0 if r["exit"] == 0 else 1


def red_ok_tests(cfg: dict, tid: str) -> set:
    return {r["test"] for r in read_journal(cfg, tid) if r.get("kind") == "red" and r.get("result") == "red-ok"}
