#!/usr/bin/env bash
# Build the Windows installer installer/Output/SpectraMaster_Setup_1.0.0.exe
#
#   bash build_exe/build_installer.sh            # full build (PyInstaller one-folder + Inno Setup)
#   bash build_exe/build_installer.sh --iss-only # only recompile the installer from the existing build
#
# Steps
#   1. icons + wizard images      (build_exe/make_icons.py, installer/make_wizard_images.py)
#   2. PyInstaller ONE-FOLDER builds (faster start-up than one-file; the LGPL Qt/SpecUtils DLLs stay
#      replaceable files in _internal\):
#        build_exe/dist_onedir/SpectraMaster/  SpectraMaster.exe + _internal\   -> {app}
#        build_exe/dist_onedir/smconvert/      smconvert.exe + _internal\       -> {app}\cli
#      The CLI keeps its OWN _internal (no PySide6) in the cli\ subfolder, so the two bundles never
#      share or overwrite each other's files.
#   3. third-party license texts  (installer/collect_licenses.py -> installer/licenses)
#   4. Inno Setup 6 compiler (ISCC) -> installer/Output/
#
# The portable one-file build is unchanged: bash build_exe/build.sh
set -euo pipefail
cd "$(dirname "$0")/.."

ISCC="${ISCC:-/c/Program Files (x86)/Inno Setup 6/ISCC.exe}"
ROOT="$(pwd -W)"
ICO="$ROOT/spectramaster/gui/spectramaster.ico"
DIST=build_exe/dist_onedir

if [[ "${1:-}" != "--iss-only" ]]; then
    python build_exe/make_icons.py
    python installer/make_wizard_images.py

    COMMON=(--paths . --collect-all SpecUtils --collect-submodules spectramaster.formats
            --collect-submodules spectramaster.analysis --collect-submodules spectramaster.tools
            --exclude-module matplotlib --exclude-module tkinter
            # large packages that may be installed in the build Python but are never imported
            # (PyInstaller would bundle them, and torch crashes its import analysis)
            --exclude-module torch --exclude-module pandas --exclude-module sympy --exclude-module numba
            --exclude-module llvmlite --exclude-module pytest --exclude-module IPython
            # optional imports of openpyxl/numpy that SpectraMaster never uses (smaller bundle,
            # and every bundled component is covered by installer/licenses)
            --exclude-module PIL --exclude-module lxml --exclude-module yaml
            --exclude-module charset_normalizer --exclude-module html5lib
            --add-data "$ROOT/spectramaster/analysis/data/gamma_library.json;spectramaster/analysis/data"
            --add-data "$ROOT/spectramaster/analysis/data/coincidence_table.json;spectramaster/analysis/data"
            --distpath "$DIST" --workpath build_exe/work_onedir --specpath build_exe/onedir_spec
            -y --clean --onedir --noupx)

    # GUI. The PDF manuals are NOT bundled here: the "User manuals" component installs them to
    # {app}\docs, where spectramaster.gui.manual.docs_dir() finds them.
    python -m PyInstaller "${COMMON[@]}" --windowed --name SpectraMaster --icon "$ICO" \
        --version-file "$ROOT/build_exe/version_gui.txt" \
        --add-data "$ROOT/spectramaster/gui/assets;spectramaster/gui/assets" \
        build_exe/gui_entry.py

    # command line tool (no Qt)
    python -m PyInstaller "${COMMON[@]}" --console --name smconvert --icon "$ICO" \
        --version-file "$ROOT/build_exe/version_cli.txt" \
        --exclude-module PySide6 build_exe/cli_entry.py

    python installer/collect_licenses.py "$DIST"
fi

# MSYS2_ARG_CONV_EXCL: stop Git Bash from turning /Qp into a path
MSYS2_ARG_CONV_EXCL="*" "$ISCC" /Qp installer/SpectraMaster.iss
ls -la installer/Output
