"""Decay correction calculator, calibration certificates and Aptec ROI reading."""
from __future__ import annotations

import math
import os
from datetime import datetime, timedelta
from pathlib import Path

import pytest

from spectramaster.analysis import decay_calc as dc
from spectramaster.analysis.certificate import Certificate, CertificateLine, list_certificates, safe_file_name

APTEC_DIR = Path(os.environ.get("SPECTRAMASTER_APTEC_DIR", r"C:\APTEC\APTEC"))


def test_activity_and_time_units():
    assert dc.convert_activity(1.0, "uCi", "Bq") == pytest.approx(37000.0)
    assert dc.convert_activity(37.0, "kBq", "uCi") == pytest.approx(1.0)
    assert dc.convert_activity(60.0, "dpm", "Bq") == pytest.approx(1.0)
    assert dc.convert_activity(1.0, "pCi", "Bq") == pytest.approx(0.037)
    assert dc.convert_time(1.0, "y", "d") == pytest.approx(365.25)
    assert dc.convert_time(90.0, "m", "h") == pytest.approx(1.5)
    with pytest.raises(ValueError):
        dc.convert_activity(1.0, "Bq", "furlong")
    with pytest.raises(ValueError):
        dc.convert_time(1.0, "s", "week")


def test_decay_correction_forward_and_back():
    hl = dc.convert_time(30.08, "y", "s")                      # Cs-137
    t0 = datetime(2000, 1, 1)
    t1 = t0 + timedelta(seconds=hl)
    assert dc.decay_correct(1000.0, hl, t0, t1) == pytest.approx(500.0)
    assert dc.decay_correct(500.0, hl, t1, t0) == pytest.approx(1000.0)
    assert dc.decay_factor(hl, 2 * hl) == pytest.approx(0.25)
    assert dc.mean_life_s(hl) == pytest.approx(hl / math.log(2))
    with pytest.raises(ValueError):
        dc.decay_factor(0.0, 10.0)
    # uncertainty: activity error only, then the half-life term ln2 * t / T * dT/T
    assert dc.decay_uncertainty(1000.0, 0.02, hl, 0.0, hl) == pytest.approx(10.0)
    u = dc.decay_uncertainty(1000.0, 0.0, hl, 0.01, hl)
    assert u == pytest.approx(500.0 * math.log(2) * 0.01)


def test_certificate_round_trip_and_match(tmp_path):
    cert = Certificate(name="Mixed gamma 2024", units="kBq", reference_time=datetime(2024, 1, 15, 12),
                       source_id="QCY48", lines=[
                           CertificateLine("Am-241", 59.54, 0.359, 1.364e10, 2.1, 1.5),
                           CertificateLine("Cs-137", 661.66, 0.851, 9.49e8, 3.0, 1.2),
                           CertificateLine("Co-60", 1173.23, 0.9985, 1.663e8, 4.0, 1.0),
                           CertificateLine("Co-60", 1332.49, 0.9998, 1.663e8, 4.0, 1.0)])
    path = cert.save(tmp_path / f"{safe_file_name(cert.name)}.json")
    assert path.name == "Mixed_gamma_2024.json"
    back = Certificate.load(path)
    assert back == cert
    assert list_certificates(tmp_path) == [path]
    assert back.match("co-60", 1332.0).energy == 1332.49
    assert back.match("Co-60", 1300.0) is None
    assert back.match("Cs-137", 661.5).activity == 3.0
    with pytest.raises(ValueError):
        Certificate(name="", lines=[]).validate()
    with pytest.raises(ValueError):
        Certificate(name="x", units="furlong").validate()
    with pytest.raises(ValueError):
        Certificate(name="x", lines=[CertificateLine("Cs-137", 661.66, 1.5)]).validate()


@pytest.mark.skipif(not (APTEC_DIR / "chern.s0").is_file(), reason="Aptec sample spectra not installed")
def test_read_aptec_rois_matches_the_stored_records():
    from spectramaster.analysis.aptec_roi import read_aptec_rois
    rois = read_aptec_rois(APTEC_DIR / "chern.s0")
    assert len(rois) >= 17
    assert rois[15] == (2992, 2997, 3014, 3049) and rois[16] == (2992, 3018, 3044, 3049)
    with pytest.raises(ValueError):
        read_aptec_rois(b"not an aptec file" * 100)
