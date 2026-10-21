"""Library defects fixed on 2026-10-21 (docs/baseline/library_lines_protocol.md): a wrong IAEA
intensity, Sandia lines duplicating IAEA lines, and IAEA daughter lines that were dropped."""
from __future__ import annotations

from spectramaster.analysis.library import load_library


def _near(nd, energy, tol=1.0):
    return [l for l in nd.lines if abs(l.energy - energy) <= tol]


def test_ac228_674_keV_is_not_2_percent():
    nd = load_library()["Ac-228"]
    assert all(l.intensity < 0.2 for l in _near(nd, 674.75, 0.2))


def test_no_transition_listed_twice():
    lib = load_library()
    # Hf-181 482 keV: 80.5 % (was 80.5 + 99.3 % from a Ta-181m duplicate)
    assert sum(l.intensity for l in _near(lib["Hf-181"], 482.1, 0.5)) < 90.0
    for name, energy in (("Sb-124", 1325.3), ("Pa-234", 1393.7), ("Ta-182", 69.3), ("Hf-175", 432.85)):
        assert len(_near(lib[name], energy, 0.45)) == 1, name
    # Np-237: the U K X-rays at 94.66 / 98.44 keV are not also listed as gammas
    np = lib["Np-237"]
    assert sum(l.intensity for l in _near(np, 98.44, 0.3)) < 20.0


def test_daughter_lines_close_to_their_own_lines_are_kept():
    lib = load_library()
    # Np-239 228.18 keV (10.7 %) next to its own 227.83 keV line, with the IAEA value
    l = max(_near(lib["Am-243"], 228.18, 0.1), key=lambda q: q.intensity)
    assert abs(l.intensity - 10.73) < 0.01
    assert any(abs(l.energy - 727.0) < 0.01 for l in lib["Te-132"].lines)
