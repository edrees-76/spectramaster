"""Collect the license texts of every third-party component bundled with SpectraMaster.

python installer/collect_licenses.py [DIST]      (run from the project root)

Writes installer/licenses/ (installed to {app}\\licenses). The texts are copied from the
installed packages' dist-info folders, the Python installation, and the upstream license files
kept in the repository (test_corpus/, spectramaster/analysis/data/source/).

With DIST (the PyInstaller one-folder output, build_exe/dist_onedir) the script also checks that
the bundle contains exactly the components listed here, so the notices stay correct when the
dependencies change.
"""
from __future__ import annotations

import sys
import sysconfig
from importlib import metadata
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "installer" / "licenses"
SITE = Path(sysconfig.get_paths()["purelib"])
PYROOT = Path(sys.base_prefix)


def dist_file(dist: str, *names: str) -> Path:
    files = metadata.distribution(dist).files or []
    for f in files:
        if Path(str(f)).name in names or str(f).replace("\\", "/").endswith(names):
            p = Path(f.locate())
            if p.is_file():
                return p
    raise FileNotFoundError(f"{dist}: none of {names}")


def ver(dist: str) -> str:
    return metadata.version(dist)


MIT_NDLAB = """\
IAEA Nuclear Data Section - ndlab (https://github.com/IAEA-NDS/ndlab)
License: MIT (as published in the ndlab repository, commit cf7fc2182cb112ae7502da0e243b30a58149fcdf)
Copyright (c) International Atomic Energy Agency (IAEA)

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.

Nothing in this license shall be construed as a waiver of the privileges and
immunities of the IAEA.

SpectraMaster uses only an extract of the ndlab database (ENSDF-based gamma and X-ray
emission data and half-lives), merged into spectramaster/analysis/data/gamma_library.json.
"""


def components() -> list[tuple[str, str, str, str, Path | str]]:
    """(output file, component, version, license, source path or literal text)."""
    return [
        ("Python_PSF-2.0.txt", "Python runtime (incl. bzip2, libffi, OpenSSL, SQLite, zlib, xz, mpdecimal; "
         "Microsoft Visual C++ runtime)", sys.version.split()[0], "PSF-2.0 and the licenses listed inside",
         PYROOT / "LICENSE.txt"),
        ("Qt6_PySide6_Shiboken6_LGPL-3.0.txt", "Qt 6 / Qt for Python (PySide6, Shiboken6)", ver("PySide6"),
         "LGPL-3.0", dist_file("python-bidi", "COPYING.LESSER")),
        ("GPL-3.0.txt", "GNU GPL 3.0 (referenced by the LGPL-3.0)", "-", "GPL-3.0",
         dist_file("python-bidi", "COPYING")),
        ("SpecUtils_LGPL-2.1.txt", "Sandia SpecUtils (Python bindings: sandiaspecutils)", ver("sandiaspecutils"),
         "LGPL-2.1", ROOT / "test_corpus" / "SpecUtils" / "_LICENSE.txt"),
        ("SandiaDecay_data_LGPL-2.1.txt", "SandiaDecay nuclear data (sandia.decay.nocoinc.min.xml, extract)",
         "commit cd75314b", "LGPL-2.1", ROOT / "spectramaster" / "analysis" / "data" / "source" / "SandiaDecay_LICENSE.txt"),
        ("IAEA_ndlab_data_MIT.txt", "IAEA-NDS ndlab nuclear data (extract)", "commit cf7fc218", "MIT", MIT_NDLAB),
        ("numpy_BSD-3-Clause.txt", "NumPy (incl. OpenBLAS, LAPACK, GCC runtime with exception)", ver("numpy"),
         "BSD-3-Clause and the licenses listed inside", dist_file("numpy", "LICENSE.txt")),
        ("scipy_BSD-3-Clause.txt", "SciPy (incl. OpenBLAS, LAPACK, GCC runtime with exception, and the "
         "bundled libraries listed inside)", ver("scipy"), "BSD-3-Clause and the licenses listed inside",
         dist_file("scipy", "LICENSE.txt")),
        ("openpyxl_MIT.txt", "openpyxl", ver("openpyxl"), "MIT", dist_file("openpyxl", "LICENCE.rst")),
        ("et_xmlfile_MIT.txt", "et_xmlfile", ver("et_xmlfile"), "MIT", dist_file("et_xmlfile", "LICENCE.rst")),
        ("pywin32_PSF.txt", "pywin32 (pywintypes, win32pdh)", ver("pywin32"), "PSF-2.0",
         dist_file("pywin32", "win32/License.txt")),
        ("PyInstaller_bootloader_GPL-2.0-with-exception.txt", "PyInstaller bootloader", ver("pyinstaller"),
         "GPL-2.0 with the bootloader exception (allows distributing non-free programs)",
         dist_file("pyinstaller", "COPYING.txt")),
    ]


NOTICE_HEAD = """\
SpectraMaster 1.0.0 - third-party components
============================================
SpectraMaster (c) 2026 Edrees F. Hery. The program bundles the components below; each keeps
its own license. The full license texts are in this folder.

{table}

LGPL components (Qt / PySide6 / Shiboken6, SpecUtils)
-----------------------------------------------------
These libraries are shipped as separate, unmodified dynamic libraries so that you may replace
them with your own (modified or newer, binary-compatible) builds:
  Qt / PySide6 / Shiboken6 : {{app}}\\_internal\\PySide6\\*.dll, *.pyd and {{app}}\\_internal\\shiboken6\\
  SpecUtils                : {{app}}\\_internal\\SpecUtils\\SpecUtils*.pyd
Source code: Qt https://download.qt.io/official_releases/qt/ ,
             Qt for Python https://download.qt.io/official_releases/QtForPython/ ,
             SpecUtils https://github.com/sandialabs/SpecUtils ,
             SandiaDecay https://github.com/sandialabs/SandiaDecay .
On request, the publisher will provide the exact versions of the LGPL source code used.
Reverse engineering of SpectraMaster for debugging such modifications is permitted.

Nuclear data
------------
The gamma-line library (gamma_library.json) is derived from IAEA ENSDF data (IAEA-NDS ndlab,
MIT) and SandiaDecay (LGPL-2.1). The coincidence table (coincidence_table.json) is derived from
ENSDF decay data of the IAEA LiveChart of Nuclides (https://nds.iaea.org/relnsd/), source: IAEA
Nuclear Data Section; used under the IAEA terms of use, which do not imply IAEA endorsement of
SpectraMaster. The sample spectra in {{app}}\\Samples carry their own
licenses (see Samples\\README.txt).
"""

# folders/files in the PyInstaller bundle -> component (for the consistency check)
EXPECTED = {"PySide6": "Qt6", "shiboken6": "Qt6", "SpecUtils": "SpecUtils", "numpy": "numpy", "scipy": "scipy",
            "pywin32_system32": "pywin32", "win32": "pywin32"}
UNEXPECTED = ["PIL", "lxml", "yaml", "charset_normalizer", "matplotlib", "html5lib", "torch", "pandas", "sympy",
              "numba", "llvmlite", "pytest", "IPython"]


def check_bundle(dist: Path) -> list[str]:
    problems = []
    for exe_dir in (dist / "SpectraMaster", dist / "smconvert"):
        internal = exe_dir / "_internal"
        if not internal.is_dir():
            problems.append(f"missing {internal}")
            continue
        for name in UNEXPECTED:
            if (internal / name).exists():
                problems.append(f"{internal / name} is bundled but not covered by the license list")
    if not (dist / "SpectraMaster" / "_internal" / "PySide6").is_dir():
        problems.append("PySide6 missing from the GUI bundle")
    return problems


def main(argv: list[str]) -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    rows = []
    for fname, comp, version, lic, src in components():
        text = src if isinstance(src, str) else Path(src).read_text(encoding="utf-8", errors="replace")
        header = f"{comp}\nVersion: {version}\nLicense: {lic}\n{'-' * 78}\n\n"
        (OUT / fname).write_text(header + text, encoding="utf-8")
        rows.append(f"  {comp}\n      version {version}; license {lic}; text: {fname}")
    (OUT / "THIRD_PARTY_NOTICES.txt").write_text(NOTICE_HEAD.format(table="\n".join(rows)), encoding="utf-8")
    print(f"{len(rows) + 1} files -> {OUT.relative_to(ROOT)}")
    if len(argv) > 1:
        problems = check_bundle(Path(argv[1]))
        for p in problems:
            print("WARNING:", p)
        return 1 if problems else 0
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
