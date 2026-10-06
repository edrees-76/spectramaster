"""Tests for the SpecUtils-backed formats (specutils_bridge.py)."""
from __future__ import annotations

import struct
from datetime import datetime
from pathlib import Path

import pytest

pytest.importorskip("SpecUtils")

from spectramaster.formats import detect_format, get_format, load_all  # noqa: E402
from spectramaster.model import Spectrum  # noqa: E402

load_all()

SAMPLE_DIR = Path("D:/الاسس و المفاهيم العامة فى استخدام برامج الطيف الجامى/اطياف مرجعية/"
                  "3- TECDOC-2026/Annex I/Detector characterization")
REAL_CNF = SAMPLE_DIR / "Cs16071k-6.CNF"


def make_spectrum(n=2048, **kw) -> Spectrum:
    d = dict(counts=[float((i * 13) % 97) for i in range(n)],
             energy_coeffs=[-0.5, 0.39, 8.6e-8], live_time=450.0, real_time=461.16,
             start_time=datetime(2016, 7, 27, 14, 6, 47), sample_id="Cs-137 test",
             description="line1\nline2", detector="HPGe-1")
    d.update(kw)
    return Spectrum(**d)


# formats that keep counts, calibration, times and start time exactly
FAITHFUL = ["ortec_chn", "ortec_spc", "iaea_spe", "ci_cnf", "n42_2006", "n42_2012",
            "gadras_pcf", "spc_ascii", "spc_float"]


def test_codes_registered():
    expected = {1: "ortec_chn", 2: "ortec_spc", 7: "iaea_spe", 10: "rms_phd", 16: "ci_cnf",
                20: "n42_2006", 21: "n42_2012", 22: "gadras_pcf", 26: "html_d3"}
    for code, key in expected.items():
        assert get_format(code).key == key
    assert get_format(10).can_read and not get_format(10).can_write
    assert get_format(26).can_write and not get_format(26).can_read
    for code in range(20, 44):
        assert 20 <= get_format(code).code <= 49


@pytest.mark.parametrize("key", FAITHFUL)
def test_roundtrip_faithful(tmp_path, key):
    fmt = get_format(key)
    sp = make_spectrum()
    p = tmp_path / ("x" + fmt.default_ext)
    fmt.writer(sp, p)
    assert detect_format(p).key == key
    r = fmt.reader(p)
    assert len(r) == 1
    r = r[0]
    assert r.counts == sp.counts
    for ch in (0, 1000, 2047):
        assert r.energy_of(ch) == pytest.approx(sp.energy_of(ch), abs=2e-3)
    assert r.live_time == pytest.approx(450.0, abs=0.02)
    assert r.real_time == pytest.approx(461.16, abs=0.02)
    assert r.start_time.replace(microsecond=0) == sp.start_time


@pytest.mark.parametrize("key", ["specutils_csv", "specutils_txt", "tka"])
def test_roundtrip_counts_only(tmp_path, key):
    fmt = get_format(key)
    sp = make_spectrum()
    p = tmp_path / ("x" + fmt.default_ext)
    fmt.writer(sp, p)
    r = fmt.reader(p)[0]
    assert r.counts == sp.counts
    if key != "tka":
        assert r.energy_of(1500) == pytest.approx(sp.energy_of(1500), abs=1e-2)


@pytest.mark.parametrize("key", ["exploranium_gr130", "exploranium_gr135"])
def test_exploranium_writes_readable_file(tmp_path, key):
    fmt = get_format(key)
    p = tmp_path / "x.dat"
    fmt.writer(make_spectrum(n=1024), p)
    r = fmt.reader(p)[0]
    assert r.num_channels in (256, 1024)
    assert detect_format(p).key == key


def test_html_written(tmp_path):
    p = tmp_path / "x.html"
    get_format("html_d3").writer(make_spectrum(), p)
    assert p.read_bytes()[:200].lower().lstrip().startswith(b"<!doctype html")


def test_chn_layout_and_calibration_convention(tmp_path):
    """Our coefficients go verbatim into the CHN trailer: E(ch) at channel number ch."""
    sp = make_spectrum(n=1024, energy_coeffs=[10.0, 0.5, 1e-5], first_channel=0)
    p = tmp_path / "a.chn"
    get_format("ortec_chn").writer(sp, p)
    b = p.read_bytes()
    assert struct.unpack_from("<h", b, 0)[0] == -1
    assert struct.unpack_from("<H", b, 30)[0] == 1024
    t = 32 + 4 * 1024
    assert struct.unpack_from("<h", b, t)[0] == -102
    c = struct.unpack_from("<3f", b, t + 4)
    assert c == pytest.approx((10.0, 0.5, 1e-5), rel=1e-6)
    assert b[16:24] == b"27JUL161"
    assert len(b) == t + 512
    r = get_format("ortec_chn").reader(p)[0]
    assert r.sample_id == "Cs-137 test" and r.detector == "HPGe-1"
    # same file through SpecUtils' own parser: identical energies
    import SpecUtils
    sf = SpecUtils.SpecFile()
    sf.loadFile(str(p), SpecUtils.ParserType.Chn)
    m = sf.measurements()[0]
    for ch in (0, 100, 900):
        assert m.gammaChannelLower(ch) == pytest.approx(r.energy_of(ch), abs=1e-3)


def test_chn_to_spe_energies_line_up(tmp_path):
    sp = make_spectrum(n=4096, energy_coeffs=[-0.564, 0.3896, 8.6e-8])
    chn, spe = tmp_path / "a.chn", tmp_path / "a.spe"
    get_format("ortec_chn").writer(sp, chn)
    a = get_format("ortec_chn").reader(chn)[0]
    get_format("iaea_spe").writer(a, spe)
    text = spe.read_text()
    assert "$ENER_FIT:" in text or "$MCA_CAL:" in text
    b = get_format("iaea_spe").reader(spe)[0]
    for ch in (0, 1698, 4095):
        assert b.energy_of(ch) == pytest.approx(sp.energy_of(ch), abs=2e-3)


def test_first_channel_is_folded_into_calibration(tmp_path):
    sp = make_spectrum(n=512, first_channel=100)
    p = tmp_path / "a.spe"
    get_format("iaea_spe").writer(sp, p)
    r = get_format("iaea_spe").reader(p)[0]
    assert r.first_channel == 0
    assert r.energy_of(0) == pytest.approx(sp.energy_of(100), abs=1e-3)


def test_unicode_output_path(tmp_path):
    d = tmp_path / "مجلد عربي"
    d.mkdir()
    p = d / "طيف.cnf"
    get_format("ci_cnf").writer(make_spectrum(), p)
    assert get_format("ci_cnf").reader(p)[0].counts == make_spectrum().counts


def test_bad_file_raises_format_error(tmp_path):
    from spectramaster.formats import FormatError
    p = tmp_path / "junk.cnf"
    p.write_bytes(b"not a spectrum at all" * 10)
    with pytest.raises(FormatError):
        get_format("ci_cnf").reader(p)
    with pytest.raises(FormatError):
        get_format("ortec_chn").reader(p)


def test_sniffers_do_not_claim_text(tmp_path):
    p = tmp_path / "plain.txt"
    p.write_text("hello\nworld\n")
    head = p.read_bytes()
    for key in ("ortec_chn", "ci_cnf", "iaea_spe", "gadras_pcf", "n42_2012", "ortec_spc"):
        assert not get_format(key).sniffer(p, head)


@pytest.mark.skipif(not REAL_CNF.exists(), reason="TECDOC sample spectra not available")
def test_real_cnf_sample():
    fmt = detect_format(REAL_CNF)
    assert fmt.key == "ci_cnf"
    s = fmt.reader(REAL_CNF)[0]
    assert s.num_channels == 8192
    assert s.total_counts == 440984
    assert s.live_time == pytest.approx(450.0)
    assert s.real_time == pytest.approx(461.162, abs=1e-3)
    # time as stored in the file (HyperLab reports 2016-Jul-27 14:06:47)
    assert s.start_time.replace(microsecond=0) == datetime(2016, 7, 27, 14, 6, 47)
    # stored Genie coefficients (-0.5641541, 0.3895932, 8.635342e-08) refer to Genie's
    # 1-based channel numbers -> re-expressed for our 0-based channels: E(i) = p(i + 1)
    p = [-0.5641541, 0.3895932, 8.635342e-08]
    assert s.energy_of(0) == pytest.approx(p[0] + p[1] + p[2], abs=1e-5)
    assert s.energy_of(1698) == pytest.approx(p[0] + p[1] * 1699 + p[2] * 1699 ** 2, abs=1e-3)
    # Cs-137 peak lands near 661.7 keV
    peak = max(range(1600, 1800), key=lambda i: s.counts[i])
    assert s.energy_of(peak) == pytest.approx(661.66, abs=1.0)
    # 10 reference lines (Cs/Co/Eu/Ba TECDOC sources): Gaussian centroids land within
    # 0.3 keV of the nuclear-data energies with the 1-based Genie convention (with the
    # raw 0-based reading they were all ~0.37 keV low)
    import math
    def centroid(sp, e):
        c = sp.energy_coeffs
        guess = int(round((e - c[0]) / c[1]))
        pk = max(range(guess - 8, guess + 9), key=lambda i: sp.counts[i])
        bg = (sum(sp.counts[pk - 8:pk - 5]) + sum(sp.counts[pk + 6:pk + 9])) / 6
        ys = [math.log(max(sp.counts[i] - bg, 1.0)) for i in (pk - 1, pk, pk + 1)]
        return pk + 0.5 * (ys[0] - ys[2]) / (ys[0] - 2 * ys[1] + ys[2])
    errs = []
    for name, lines in (("Cs16071k-6.CNF", [661.657]), ("Co16065k-6.CNF", [1173.228, 1332.492]),
                        ("Eu16065k-6.CNF", [121.7817, 344.2785, 778.9045, 964.057, 1408.013]),
                        ("Ba16065k-6.CNF", [356.0129])):
        sp = fmt.reader(SAMPLE_DIR / name)[0]
        errs += [sp.energy_of(centroid(sp, e)) - e for e in lines]
    assert abs(sum(errs) / len(errs)) < 0.1
    assert max(abs(e) for e in errs) < 0.3


@pytest.mark.skipif(not REAL_CNF.exists(), reason="TECDOC sample spectra not available")
@pytest.mark.parametrize("key", ["ortec_chn", "iaea_spe", "ci_cnf", "n42_2012", "gadras_pcf"])
def test_real_cnf_converts(tmp_path, key):
    src = get_format("ci_cnf").reader(REAL_CNF)[0]
    fmt = get_format(key)
    p = tmp_path / ("out" + fmt.default_ext)
    fmt.writer(src, p)
    r = fmt.reader(p)[0]
    assert r.counts == src.counts
    for i in (0, 1698, 8191):
        assert r.energies()[i] == pytest.approx(src.energies()[i], abs=5e-3)
    assert abs((r.start_time - src.start_time).total_seconds()) < 1


# ------------------------------------------------------------- CNF / Genie-2000
def test_cnf_pads_to_power_of_two_and_keeps_metadata(tmp_path):
    sp = make_spectrum(n=1000, description="first line\nsecond line")
    p = tmp_path / "pad.cnf"
    get_format("ci_cnf").writer(sp, p)
    r = get_format("ci_cnf").reader(p)[0]
    assert r.num_channels == 1024
    assert r.counts[:1000] == sp.counts and not any(r.counts[1000:])
    assert r.sample_id == "Cs-137 test"
    assert r.description == "first line\nsecond line"
    assert r.detector == "HPGe-1"
    assert r.start_time == sp.start_time


def test_cnf_higher_order_calibration_fitted_to_quadratic(tmp_path):
    sp = make_spectrum(n=4096, energy_coeffs=[1.24, 0.326, -1.18e-6, 1.7e-10])
    p = tmp_path / "cubic.cnf"
    get_format("ci_cnf").writer(sp, p)
    r = get_format("ci_cnf").reader(p)[0]
    assert len(r.energy_coeffs) == 3
    worst = max(abs(r.energy_of(c) - sp.energy_of(c)) for c in range(0, 4096, 64))
    assert worst < 1.0


def test_cnf_65536_channels_native_fallback(tmp_path):
    sp = make_spectrum(n=65536)
    p = tmp_path / "big.cnf"
    get_format("ci_cnf").writer(sp, p)
    r = get_format("ci_cnf").reader(p)[0]
    assert r.counts == sp.counts and r.live_time == 450.0


GENIE = Path("C:/GENIE2K/EXEFILES")
needs_genie = pytest.mark.skipif(not (GENIE / "movedata.exe").exists()
                                 or not (GENIE / "filecnvt.exe").exists(),
                                 reason="Canberra Genie-2000 not installed")


def _genie_dir() -> Path:
    # Genie's VDM service writes the output: it cannot use pytest's owner-only tmp_path
    import os
    import tempfile
    import uuid
    d = Path(tempfile.gettempdir()) / f"spectramaster_genie_{uuid.uuid4().hex[:10]}"
    os.makedirs(d)
    return d


def _genie(tool: str, *args: str) -> str:
    import subprocess
    r = subprocess.run([str(GENIE / tool), *args], capture_output=True, text=True, timeout=180)
    return f"rc={r.returncode} {r.stdout} {r.stderr}"


@needs_genie
@pytest.mark.parametrize("n", [1024, 4096, 16384])
def test_genie_reads_our_cnf(n):
    """Genie MOVEDATA must parse our CNF and rewrite it with identical data."""
    import shutil
    sp = make_spectrum(n=n, description="desc one\ndesc two")
    w = _genie_dir()
    try:
        src, dst = w / "ours.cnf", w / "genie_copy.cnf"
        get_format("ci_cnf").writer(sp, src)
        msg = _genie("movedata.exe", str(src), str(dst))
        assert dst.exists(), msg
        r = get_format("ci_cnf").reader(dst)[0]
        assert r.counts == sp.counts
        assert r.live_time == pytest.approx(450.0, abs=0.01)
        assert r.real_time == pytest.approx(461.16, abs=0.01)
        assert r.energy_of(1000) == pytest.approx(sp.energy_of(1000), abs=0.01)
        assert r.start_time == sp.start_time
        assert r.sample_id == "Cs-137 test" and r.description == "desc one\ndesc two"
        out = _genie("getpars.exe", str(src), "/SDESC2")
        assert "desc two" in out, out
        out = _genie("getpars.exe", str(src), "/ELIVE")
        assert "450 secs" in out, out
    finally:
        shutil.rmtree(w, ignore_errors=True)


@needs_genie
def test_genie_imports_our_chn():
    import shutil
    sp = make_spectrum(n=4096)
    w = _genie_dir()
    try:
        src, dst = w / "ours.chn", w / "from_chn.cnf"
        get_format("ortec_chn").writer(sp, src)
        msg = _genie("filecnvt.exe", str(src), str(dst), "/ORTEC")
        assert dst.exists(), msg
        r = get_format("ci_cnf").reader(dst)[0]
        assert r.counts == sp.counts
        assert (r.live_time, r.real_time) == (450.0, 461.16)
        # FILECNVT copies the ORTEC coefficients verbatim although Genie numbers channels
        # from 1, so Genie's energies are one channel off: E_genie(i) = p(i + 1)
        p = sp.energy_coeffs
        for i in (0, 1000, 4095):
            assert r.energy_of(i) == pytest.approx(sp.energy_of(i + 1), abs=1e-3)
        assert r.start_time == sp.start_time and r.sample_id == "Cs-137 test"
    finally:
        shutil.rmtree(w, ignore_errors=True)


# ------------------------------------------------------------- time zone handling
@pytest.mark.parametrize("key", ["iaea_spe", "ortec_spc", "spc_float", "spc_ascii", "n42_2006",
                                 "n42_2012", "gadras_pcf", "specutils_txt"])
def test_wall_clock_time_written_verbatim(tmp_path, key):
    """The file must contain the wall-clock time we pass in, whatever the local TZ."""
    fmt = get_format(key)
    sp = make_spectrum(start_time=datetime(2019, 6, 30, 23, 30, 5))
    p = tmp_path / ("t" + fmt.default_ext)
    fmt.writer(sp, p)
    assert fmt.reader(p)[0].start_time.replace(microsecond=0) == sp.start_time
    if key == "iaea_spe":
        assert "06/30/2019 23:30:05" in p.read_text()
    if key.startswith("n42_2012"):
        assert "2019-06-30T23:30:05" in p.read_text()


def test_spe_time_read_as_written():
    f = Path(__file__).resolve().parent.parent / "test_corpus" / "pyne" / "tests" / "gv_format_spect.spe"
    if not f.exists():
        pytest.skip("pyne sample not in corpus")
    assert "08/01/2014 11:43:41" in f.read_text(errors="replace")
    s = get_format("iaea_spe").reader(f)[0]
    assert s.start_time == datetime(2014, 8, 1, 11, 43, 41)


CORPUS = Path(__file__).resolve().parent.parent / "test_corpus"


@pytest.mark.skipif(not (CORPUS / "SpecUtils").exists(), reason="test corpus not present")
def test_n42_utc_time_keeps_utc_wall_clock():
    f = next((CORPUS / "SpecUtils").rglob("Mn56_DetX_Shielded.n42"), None)
    if f is None:
        pytest.skip("Mn56_DetX_Shielded.n42 not in corpus")
    assert "21:15:00Z" in f.read_text(errors="replace")
    s = detect_format(f).reader(f)[0]
    assert (s.start_time.hour, s.start_time.minute) == (21, 15)


# --------------------------------------------------------------- CHN quirks
def _chn_bytes(date: bytes, secs: bytes, extra: bytes = b"") -> bytes:
    n = 16
    head = struct.pack("<hHH", -1, 0, 1) + secs + struct.pack("<ii", 100, 50) + date + b"1908"
    head += struct.pack("<HH", 0, n)
    trailer = bytearray(512)
    struct.pack_into("<hh3f", trailer, 0, -102, 0, 1.0, 2.0, 0.0)
    return head + struct.pack(f"<{n}I", *range(n)) + bytes(trailer) + extra


@pytest.mark.parametrize("date,secs,want", [
    (b"30MAY85 ", b"\x00\x00", datetime(1985, 5, 30, 19, 8, 0)),
    (b"30MAY85\x00", b"07", datetime(1985, 5, 30, 19, 8, 7)),
    (b"30MAY161", b"07", datetime(2016, 5, 30, 19, 8, 7)),
    (b"30MAY16\x00", b"07", datetime(2016, 5, 30, 19, 8, 7)),
    (b"30MAY960", b"07", datetime(1996, 5, 30, 19, 8, 7)),
])
def test_chn_date_quirks(tmp_path, date, secs, want):
    p = tmp_path / "q.chn"
    p.write_bytes(_chn_bytes(date, secs))
    assert get_format("ortec_chn").reader(p)[0].start_time == want


def test_chn_sniffer_accepts_extra_bytes_after_trailer(tmp_path):
    p = tmp_path / "x.chn"
    p.write_bytes(_chn_bytes(b"30MAY161", b"00", extra=b"\x00" * 17000))
    assert detect_format(p).key == "ortec_chn"
    bad = tmp_path / "y.chn"
    bad.write_bytes(_chn_bytes(b"30MAY161", b"00")[:32 + 64] + b"\x01\x02" + b"\x00" * 17000)
    assert not get_format("ortec_chn").sniffer(bad, bad.read_bytes()[:4096])


# ----------------------------------------------------------------- N42 dialects
def test_n42_radiological_root_lenient(tmp_path):
    p = tmp_path / "r.n42"
    p.write_text('<?xml version="1.0"?><RadiologicalInstrumentData xmlns="http://physics.nist.gov/N42/2006/N42">'
                 "<MeasurementGroup><Measurement><Spectrum><EnergyCalibration>"
                 "<CalibrationEquation>List</CalibrationEquation><ChannelEnergies>5 5.5 6 6.5</ChannelEnergies>"
                 "</EnergyCalibration><ChannelData>1 2 3 4</ChannelData><LiveTime>295</LiveTime>"
                 "<RealTime>PT300S</RealTime><StartTime>2020-01-02T03:04:05Z</StartTime>"
                 "</Spectrum></Measurement></MeasurementGroup></RadiologicalInstrumentData>")
    fmt = detect_format(p)
    assert fmt.key == "n42_2006"
    s = fmt.reader(p)[0]
    assert s.counts == [1, 2, 3, 4] and s.live_time == 295 and s.real_time == 300
    assert s.start_time == datetime(2020, 1, 2, 3, 4, 5)
    assert s.energy_of(3) == pytest.approx(6.5, abs=1e-3)


@pytest.mark.skipif(not (CORPUS / "RASE").exists(), reason="test corpus not present")
def test_rase_foreground_first():
    f = CORPUS / "RASE/tests/example_base/multisec/VTest_MTest_Co60_multisec.n42"
    if not f.exists():
        pytest.skip("RASE multisec sample missing")
    spectra = detect_format(f).reader(f)
    assert spectra[0].extra.get("source_type") == "Foreground"
    assert "Background" in [s.extra.get("source_type") for s in spectra]
