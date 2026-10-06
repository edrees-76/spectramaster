"""Shared helpers for test_ascii_formats.py / test_canberra_legacy.py."""
from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
import uuid
from datetime import datetime
from pathlib import Path

from spectramaster.model import Spectrum

REF = Path("D:/الاسس و المفاهيم العامة فى استخدام برامج الطيف الجامى/اطياف مرجعية")
G1_ASC = REF / "1- IAEA G-1" / "الأطياف ASCII"
SANDERSON = REF / "2- Sanderson" / "الأطياف"
TECDOC_ASC = REF / "3- TECDOC-2026" / "Annex I" / "Detector characterization" / "HPGe-CA6C_Spectra-ASC"
LAB_IEC = Path("D:/مختبر التحاليل و القياسات الاشعاعية/04_القياسات_والبيانات_الفنية/"
               "01_أرشيف_وحدة_القياسات/الأرشيف_كما_ورد/شغل قديم القوارشة + الصابرى/شغل سابق")
FILECNVT = Path("C:/GENIE2K/EXEFILES/filecnvt.exe")


def synthetic(n: int = 1030, calibrated: bool = True) -> Spectrum:
    counts = [int(50 + 3 * (i % 17) + (5000 if 400 <= i <= 404 else 0)) for i in range(n)]
    return Spectrum(
        counts=counts,
        energy_coeffs=[0.5, 0.25, 1e-6] if calibrated else [],
        live_time=1234.5, real_time=1300.25,
        start_time=datetime(2024, 3, 7, 14, 5, 9),
        sample_id="Soil sample 42", description="line two\nline three",
        detector="HPGE1")


def genie_to_cnf(src: Path, qualifier: str):
    """Convert `src` with Canberra Genie 2000 FILECNVT and return the first
    SpecUtils measurement of the resulting CNF, or None if Genie is unavailable.

    Genie's VDM service creates the output file; inside pytest's owner-only
    (mode 0o700) tmp_path the result is unreadable to us, so the conversion runs
    in a temp directory created with default permissions."""
    if not FILECNVT.exists():
        return None
    import SpecUtils
    work = Path(tempfile.gettempdir()) / f"spectramaster_genie_{uuid.uuid4().hex[:10]}"
    os.makedirs(work)
    try:
        inp = work / ("in" + src.suffix)
        shutil.copyfile(src, inp)
        out = work / "out.CNF"
        r = subprocess.run([str(FILECNVT), str(inp), str(out), qualifier],
                           capture_output=True, text=True, timeout=120)
        if r.returncode != 0 or not out.exists():
            raise AssertionError(f"FILECNVT {qualifier} failed: {r.stdout} {r.stderr}")
        f = SpecUtils.SpecFile()
        f.loadFile(str(out), SpecUtils.ParserType.Cnf)
        return f.measurements()[0]
    finally:
        shutil.rmtree(work, ignore_errors=True)


def copy_to(tmp: Path, src: Path, name: str) -> Path:
    dst = tmp / name
    shutil.copyfile(src, dst)
    return dst
