"""Spectrum format plug-ins.

Code allocation (keep in sync with the module that registers each one):

  DataMaster-compatible codes (same numbers as ORTEC DataMaster -i/-j):
     1 ortec_chn        ORTEC ADCAM *.chn            specutils_bridge.py
     2 ortec_spc        ORTEC INFORM *.spc           specutils_bridge.py
     5 ascii1           ASCII-1 *.txt (1 count/line) ascii_formats.py
     6 ascii2           ASCII-2 *.txt (chan, counts) ascii_formats.py
     7 iaea_spe         IAEA/Rossendorf SPE *.spe    specutils_bridge.py
     8 iec1455          IEC 1455 ASCII *.iec         ascii_formats.py
     9 ieee_asc         IEEE ASCII *.asc             ascii_formats.py
    10 rms_phd          RMS/IMS ASCII *.phd          specutils_bridge.py
    13 aptec_s0         APTEC v6.3 *.s0              aptec.py
    14 ci_s100          Canberra S100 *.mca          canberra_legacy.py
    15 ci_accuspec      Canberra AccuSpec *.dat      canberra_legacy.py (read only)
    16 ci_cnf           Canberra CAM *.cnf           specutils_bridge.py
  (3, 4, 11, 12 = Oxford PCA-2/PCA-3, LLNL, SAMPO 90: reserved, not implemented --
   no public documentation or sample files)

  Extra formats:
    17 eml_sanderson    EML/Sanderson ASCII *.dat    canberra_legacy.py (read only)
    20-49  specutils_bridge.py (N42, PCF, CSV, TKA, HTML, vendor read-only formats ...)
    50-59  extra_formats.py (Excel .xlsx, JSON, ...)
    70-79  aptec_import_binary.py (binary formats of the Aptec MCA v6.31 converter DLLs):
           70 jcac_vax R/W, 71 nd66 R/W, 72 norland5000 R/W, 73 oxford_ans R/W,
           74 quantrad_scout, 75 spectran_f, 76 nucleus_pca (.spm), 77 pca_multiport (.spt),
           78 aptec_v30, 79 aptec_v43 (read only).  76/77 are probably DataMaster's
           Oxford PCA-2/PCA-3 (codes 3/4) but that is unconfirmed, so 3/4 stay reserved.
    80 lab_dat1670       EMCA2000 binary *.dat, 1670-byte text header (laboratory HPGe files
           2004-2009; layout inferred)  lab_binary_dat.py (read only)
    60-69  aptec_import_ascii.py -- text formats of the Aptec MCA v6.31 import DLLs:
           60 aptec_ascii *.apt, 61 bti_ascii *.bti (read only), 62 chandata_csv *.csv,
           63 ci90_ascii *.o (read only), 64 davidson_ascii *.dav, 65 iaea_ascii_dat *.dat,
           66 npl_ascii *.txt, 67 rump_ascii *.mac, 68 wallac_ascii *.001, 69 laval_ascii *.de1
"""
from __future__ import annotations

import importlib
import logging

from .base import (FormatError, FormatSpec, all_formats, detect_format, get_format,
                   readable_formats, register, writable_formats)

_MODULES = [
    "specutils_bridge",
    "aptec",
    "ascii_formats",
    "canberra_legacy",
    "extra_formats",
    "aptec_import_ascii",
    "aptec_import_binary",
    "lab_binary_dat",
]

_loaded = False
log = logging.getLogger(__name__)


def load_all() -> None:
    """Import every format module so they register themselves (idempotent)."""
    global _loaded
    if _loaded:
        return
    for name in _MODULES:
        try:
            importlib.import_module(f"{__name__}.{name}")
        except Exception as exc:  # missing dependency or broken module -> skip it, keep the rest
            log.warning("format module %s not loaded: %s", name, exc)
    _loaded = True


__all__ = [
    "FormatError", "FormatSpec", "all_formats", "detect_format", "get_format",
    "readable_formats", "register", "writable_formats", "load_all",
]
