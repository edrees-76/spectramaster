#!/usr/bin/env bash
# Build SpectraMaster.exe (GUI) and smconvert.exe (command line) into build_exe/dist.
# Run from the project root:  bash build_exe/build.sh
# This is the PORTABLE one-file build. The Windows installer (one-folder build + Inno Setup)
# is built by build_exe/build_installer.sh.
set -euo pipefail
cd "$(dirname "$0")/.."

python build_exe/make_icons.py   # logo.jpg -> gui/assets/*.png + gui/spectramaster.ico

ROOT="$(pwd -W)"
ICO="$ROOT/spectramaster/gui/spectramaster.ico"
COMMON=(--paths . --collect-all SpecUtils --collect-submodules spectramaster.formats --collect-submodules spectramaster.analysis --collect-submodules spectramaster.tools
        --exclude-module matplotlib --exclude-module tkinter
        --add-data "$ROOT/spectramaster/analysis/data/gamma_library.json;spectramaster/analysis/data"
        --add-data "$ROOT/spectramaster/analysis/data/coincidence_table.json;spectramaster/analysis/data"
        --distpath build_exe/dist --workpath build_exe/work --specpath build_exe -y --onefile)

python -m PyInstaller "${COMMON[@]}" --windowed --name SpectraMaster --icon "$ICO" \
    --version-file "$ROOT/build_exe/version_gui.txt" \
    --add-data "$ROOT/spectramaster/gui/assets;spectramaster/gui/assets" \
    --add-data "$ROOT/docs/SpectraMaster_User_Manual_AR.pdf;docs" \
    --add-data "$ROOT/docs/SpectraMaster_User_Manual_EN.pdf;docs" \
    build_exe/gui_entry.py

python -m PyInstaller "${COMMON[@]}" --console --name smconvert --icon "$ICO" \
    --version-file "$ROOT/build_exe/version_cli.txt" \
    --exclude-module PySide6 build_exe/cli_entry.py

ls -la build_exe/dist
