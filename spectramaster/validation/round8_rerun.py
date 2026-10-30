"""Round-8 review, Codex M6 / Gemini M2: re-runs of the round-7 harnesses, historical and on the
current engine, the committed results left as they are (docs/baseline/round8_rerun_protocol.md).

    python -m spectramaster.validation.round8_rerun [--rerun]

For each round-7 harness: its committed results (``docs/baseline/after_R7x``); a historical run at
the merge commit of its batch (a temporary git worktree, the harness as it was); a run on the
current code with ``--rerun`` (results in the temporary folder).  A criterion whose state on the
current code differs from the historical one is assigned to the first later merge commit of main
(first parent) at which it differs.  Results to ``docs/baseline/after_R8G`` (``--rerun``: RERUN in
the temporary folder).  Needs git and the repository's history; runs the harnesses as subprocesses.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "docs" / "baseline" / "after_R8G"
RERUN = Path(tempfile.gettempdir()) / "spectramaster_round8_rerun"
# (harness, its committed folder, the merge commit of its batch)
HARNESSES = (("round7_tcs_refit", "after_R7A", "1d610ac"), ("round7_combined", "after_R7B", "0b95938"),
             ("round7_shared_background", "after_R7C", "3cd2aa7"), ("round7_quad_limits", "after_R7D", "27a54b1"),
             ("round7_inputs", "after_R7E", "2469fda"))


def _git(*args, cwd=ROOT) -> str:
    return subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True, text=True).stdout.strip()


def _states(md: str) -> dict:
    """{criterion: "PASS" | "FAIL"} of a harness's results table."""
    out = {}
    for line in md.splitlines():
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if len(cells) >= 3 and cells[-1] in ("PASS", "FAIL") and cells[0] != "ID":
            out[cells[0]] = cells[-1]
    return out


def _exec(cmd, cwd, env) -> tuple:
    p = subprocess.run(cmd, cwd=cwd, env=env, capture_output=True, text=True)
    return p.returncode, p.stdout, p.stderr


def _run(mod: str, cwd: Path, rerun: bool, md: Path) -> dict:
    """Run the harness and read the states it writes to `md`: removed first, so only a file written by
    this run counts, and only with exit 0 or 1 (round9_harness_protocol.md)."""
    md.unlink(missing_ok=True)
    env = dict(os.environ, PYTHONPATH=str(cwd), QT_QPA_PLATFORM="offscreen", PYTHONHASHSEED="0")
    cmd = [sys.executable, "-B", "-m", f"spectramaster.validation.{mod}"] + (["--rerun"] if rerun else [])
    code, _out, err = _exec(cmd, cwd, env)
    r = {"exit": code, "stderr_tail": err.strip().splitlines()[-3:] if code not in (0, 1) else [], "states": {}}
    if code not in (0, 1):
        r["error"] = f"exit {code}"
    elif not md.exists():
        r["error"] = "no results file written"
    else:
        r["states"] = _states(md.read_text(encoding="utf-8"))
    return r


def _rerun_md(mod: str) -> Path:
    return Path(tempfile.gettempdir()) / f"spectramaster_{mod}" / f"{mod}.md"


def _at_commit(mod: str, folder: str, sha: str) -> dict:
    """The harness run at commit `sha` in a temporary worktree: its exit and states."""
    tmp = Path(tempfile.mkdtemp(prefix="sm_r8g_"))
    wt = tmp / "wt"
    _git("worktree", "add", "--detach", str(wt), sha)
    try:
        r = _run(mod, wt, False, wt / "docs" / "baseline" / folder / f"{mod}.md")
    finally:
        _git("worktree", "remove", "--force", str(wt))
    return r


def _digests(folder: str) -> dict:
    d = ROOT / "docs" / "baseline" / folder
    return {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(d.iterdir()) if p.is_file()}


def collect() -> dict:
    head = _git("rev-parse", "--short", "HEAD")
    res = {"head": head, "harnesses": {}}
    for mod, folder, sha in HARNESSES:
        before = _digests(folder)
        committed = _states(_git("show", f"HEAD:docs/baseline/{folder}/{mod}.md"))
        cur = _run(mod, ROOT, True, _rerun_md(mod))
        after = _digests(folder)
        hist = _at_commit(mod, folder, sha)
        changed = sorted(k for k in set(hist["states"]) | set(cur["states"])
                         if hist["states"].get(k) != cur["states"].get(k))
        assigned, steps = {}, []
        if changed:
            later = _git("rev-list", "--first-parent", "--merges", "--reverse", f"{sha}..HEAD").split()
            for c in later:
                r = _at_commit(mod, folder, c)
                steps.append({"commit": c[:7], "subject": _git("log", "-1", "--format=%s", c), "exit": r["exit"],
                              "states": r["states"], "error": r.get("error")})
                if r.get("error"):
                    continue
                for k in changed:
                    if k not in assigned and r["states"].get(k) != hist["states"].get(k):
                        assigned[k] = c[:7]
                if len(assigned) == len(changed):
                    break
        res["harnesses"][mod] = {"folder": folder, "merge": sha, "committed": committed, "historical": hist,
                                 "current": cur, "changed": changed, "assigned": assigned, "steps": steps,
                                 "committed_files_unchanged": before == after}
    return res


def criteria(res: dict) -> dict:
    h = res["harnesses"]
    out = {}
    bad = [m for m, r in h.items() if not r["committed_files_unchanged"]]
    out["RG8.C1"] = {"value": ("; ".join(bad) + ": committed files changed") if bad else
                     "every committed after_R7x file byte-identical after the --rerun runs", "pass": not bad}
    vals, ok = [], True
    for m, r in h.items():
        same = r["historical"]["states"] == r["committed"] and bool(r["committed"])
        ok &= same
        n = sum(v == "PASS" for v in r["historical"]["states"].values())
        vals.append(f"{m} at {r['merge']}: {n} PASS / {len(r['historical']['states']) - n} FAIL"
                    + ("" if same else f" (committed {r['committed']})")
                    + (f" (error: {r['historical']['error']})" if r["historical"].get("error") else ""))
    out["RG8.C2"] = {"value": "; ".join(vals), "pass": ok}
    vals, ok = [], True
    for m, r in h.items():
        n = sum(v == "PASS" for v in r["current"]["states"].values())
        txt = f"{m} at {res['head']}: {n} PASS / {len(r['current']['states']) - n} FAIL"
        if r["changed"]:
            txt += " (" + ", ".join(f"{k} {r['historical']['states'].get(k)} -> {r['current']['states'].get(k)} from "
                                    f"{r['assigned'].get(k, 'unassigned')}" for k in r["changed"]) + ")"
        if r["current"].get("error"):
            txt += f" (error: {r['current']['error']})"
        ok &= bool(r["current"]["states"]) and all(k in r["assigned"] for k in r["changed"])
        vals.append(txt)
    out["RG8.C3"] = {"value": "; ".join(vals), "pass": ok}
    return out


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--rerun", action="store_true", help=f"write the results to {RERUN}, not after_R8G")
    a = ap.parse_args(argv)
    res = collect()
    crit = criteria(res)
    out = RERUN if a.rerun else OUT
    out.mkdir(parents=True, exist_ok=True)
    (out / "round8_rerun.json").write_text(json.dumps({"results": res, "criteria": crit}, indent=1,
                                                     ensure_ascii=False), encoding="utf-8")
    lines = ["# Round-8 re-runs of the round-7 harnesses (Codex M6, Gemini M2)", "", f"HEAD {res['head']}", "",
             "| ID | value | result |", "|---|---|---|"]
    lines += [f"| {k} | {v['value']} | {'PASS' if v['pass'] else 'FAIL'} |" for k, v in crit.items()]
    steps = [f"- {m} at {s['commit']} ({s['subject']}): exit {s['exit']}, "
             + (f"error: {s['error']}, " if s.get("error") else "")
             + ", ".join(f"{k} {v}" for k, v in sorted(s["states"].items()))
             for m, r in res["harnesses"].items() for s in r["steps"]]
    if steps:
        lines += ["", "Runs at the later merge commits:", ""] + steps
    (out / "round8_rerun.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    n = sum(v["pass"] for v in crit.values())
    print("\n".join(lines))
    print(f"{n} PASS / {len(crit) - n} FAIL")
    return 0 if n == len(crit) else 1


if __name__ == "__main__":
    sys.exit(main())
