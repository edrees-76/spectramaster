"""Batch analysis grouped by compatible conditions (Release F, F2)."""
from __future__ import annotations

from dataclasses import replace

from spectramaster.analysis import efficiency as eff
from spectramaster.convert import resolve_format, write_spectrum
from spectramaster.lab.batch import BatchSetup, group_items, run_batch, scan, write_csv
from spectramaster.lab.detector import MeasurementGeometry
from spectramaster.validation import scenarios
from spectramaster.validation.synthetic import HPGE, NAI, Continuum, TruePeak, make_spectrum


def _files(tmp_path):
    fmt = resolve_format("aptec_s0")
    out = []
    for i, (det, gain_err) in enumerate([(HPGE, 0.0), (HPGE, 0.0), (HPGE, 0.003), (NAI, 0.0)]):
        s = make_spectrum(det, [TruePeak(661.657, 2e4), TruePeak(1460.8, 5e3)], Continuum(300, 400, 10), 30 + i,
                          gain_error=gain_err).spectrum
        p = tmp_path / f"s{i}.s0"
        write_spectrum(s, p, fmt)
        out.append(p)
    (tmp_path / "broken.s0").write_bytes(b"not a spectrum")
    return out + [tmp_path / "broken.s0"]


def test_groups_by_detector_channels_and_calibration(tmp_path):
    items = scan(_files(tmp_path))
    assert sum(1 for it in items if it.error) == 1
    groups = group_items(items)
    sizes = sorted(len(g.items) for g in groups)
    assert sizes == [1, 1, 2]            # two identical HPGe, one with a 0.3 % gain change, one NaI


def test_unassigned_groups_are_not_analysed_and_geometry_is_guarded(tmp_path):
    groups = group_items(scan(_files(tmp_path)))
    syn, cert = next(scenarios.efficiency_calibration(HPGE, 1))
    curve = eff.fit_efficiency(eff.measure_efficiency(syn.spectrum, cert), "two_branch", crossover="auto")
    curve.geometry_record = MeasurementGeometry("point 10 cm", kind="point", source_distance_mm=100.0).to_dict()
    big = max(groups, key=lambda g: len(g.items))
    ok = BatchSetup(curve=curve, geometry=MeasurementGeometry("point 10 cm", kind="point", source_distance_mm=100.0),
                    nuclides=["Cs-137", "K-40"])
    rows = run_batch(groups, {big.id: ok})
    assigned = [r for r in rows if r["group"] == big.id]
    assert assigned and all(r["status"] == "analysed" for r in assigned)
    assert {r["nuclide"] for r in assigned} == {"Cs-137", "K-40"}
    others = [r for r in rows if r["group"] != big.id]
    assert others and all(r["status"].startswith("not analysed") for r in others)
    bad = replace(ok, geometry=MeasurementGeometry("Marinelli", kind="marinelli"))
    rows = run_batch([big], {big.id: bad})
    assert all(r["status"].startswith("refused") for r in rows)
    p = write_csv(tmp_path / "out.csv", rows)
    assert p.read_text(encoding="utf-8-sig").splitlines()[0].startswith("file,index,group")


def test_every_file_gets_a_row_even_without_identification():
    from spectramaster.lab.batch import BatchGroup, BatchItem, BatchSetup, run_batch
    from spectramaster.validation.benchmark import _flat_curve
    from spectramaster.validation.synthetic import HPGE, Continuum, make_spectrum
    s = make_spectrum(HPGE, [], Continuum(300, 400, 10), 5).spectrum
    g = BatchGroup(1, "det", len(s.counts), list(s.energy_coeffs), [BatchItem("empty.spe", 0, s, "det", len(s.counts))])
    rows = run_batch([g], {1: BatchSetup(curve=_flat_curve())})
    assert len(rows) == 1 and rows[0]["status"] == "no nuclide identified"
