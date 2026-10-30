"""Round-9 review, Codex M3 / M4 and Gemini M1: re-run reliability of the round-7 and round-8 harnesses
(docs/baseline/round9_harness_protocol.md)."""
from __future__ import annotations

import math
import shutil
import subprocess
import tempfile

import pytest

from spectramaster.analysis import activity as act
from spectramaster.validation import compare
from spectramaster.validation import round7_quad_limits as rq
from spectramaster.validation import round8_alt_limits, round8_coi_guard, round8_peak_mode
from spectramaster.validation import round8_rerun as rr


def test_same_tolerates_the_last_bits_only():
    a = {"x": [0.32502132337030615, 1, None, "n"], "y": {"z": float("nan")}}
    b = {"x": [0.32502132337030804, 1, None, "n"], "y": {"z": float("nan")}}
    assert compare.same(a, b)
    assert not compare.same(a, {"x": [0.3250213237, 1, None, "n"], "y": {"z": float("nan")}})
    assert not compare.same({"x": 0.0}, {"x": 1e-300})
    assert not compare.same({"x": True}, {"x": 1})
    assert not compare.same({"x": 1}, {"x": 1, "y": 2})
    assert not compare.same([1, 2], [1, 2, 3])


@pytest.mark.parametrize("mod", [round8_alt_limits, round8_peak_mode, round8_coi_guard])
def test_round8_controls_use_the_tolerance(mod):
    v = {"lines": [{"mda": 0.1, "note": "x"}], "n": 3}
    assert mod._same(v, {"lines": [{"mda": 0.1 * (1 + 1e-13), "note": "x"}], "n": 3})
    assert not mod._same(v, {"lines": [{"mda": 0.1 * (1 + 1e-9), "note": "x"}], "n": 3})


def _has_commit(sha: str) -> bool:
    if shutil.which("git") is None:
        return False
    return subprocess.run(["git", "cat-file", "-e", f"{sha}^{{commit}}"], cwd=rr.ROOT,
                          capture_output=True).returncode == 0


@pytest.mark.skipif(not _has_commit("2469fda"), reason="needs git and the repository's history")
def test_rerun_ignores_a_stale_artifact(monkeypatch, tmp_path):
    """A harness run that fails before writing reports no states, whatever files are present."""
    monkeypatch.setattr(tempfile, "tempdir", str(tmp_path))
    stale = tmp_path / "spectramaster_round7_inputs"
    stale.mkdir()
    (stale / "round7_inputs.md").write_text("| ID | value | result |\n|---|---|---|\n| RE.C1 | x | PASS |\n",
                                            encoding="utf-8")
    monkeypatch.setattr(rr, "HARNESSES", (("round7_inputs", "after_R7E", "2469fda"),))
    monkeypatch.setattr(rr, "_exec", lambda cmd, cwd, env: (99, "", "boom"))
    res = rr.collect()
    h = res["harnesses"]["round7_inputs"]
    assert h["current"]["states"] == {} and h["historical"]["states"] == {}
    assert h["current"]["exit"] == 99 and h["current"]["error"]
    crit = rr.criteria(res)
    assert not crit["RG8.C2"]["pass"] and not crit["RG8.C3"]["pass"]


def test_quad_recombination_keeps_the_window_coefficients():
    """The Ba-133 mean's limits equal combined_limits of the quadratic lines' own limits, cross terms
    included (engine 1.34.0)."""
    for m in rq.METHODS:
        c = rq._case(rq.NAI, None, 7, ["Ba-133"], "mean", m)
        nr = c["nuclides"][0]
        assert sum(rq._quad(l) for l in c["lines"]) >= 2
        assert math.isclose(nr["decision_threshold"], nr["recombined"][0], rel_tol=1e-9)
        assert math.isclose(nr["mda"], nr["recombined"][1], rel_tol=1e-9)


def test_copied_line_keeps_its_coefficients():
    from spectramaster.validation import primary as pr
    sp = rq._spectrum(rq.NAI)
    res = act.compute_activities(sp, pr._flat_curve(), rq._opt(["Ba-133"], "currie", method="mean"))
    ln = [l for l in res.nuclides[0].lines if getattr(l, "_cov_res", None) is not None][0]
    cp = rq._replace(ln, mda=1.0)
    assert cp.mda == 1.0 and cp._cov_res is ln._cov_res and cp._ref_vec is ln._ref_vec
