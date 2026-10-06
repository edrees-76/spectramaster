"""Tests for the command line (spectramaster.cli)."""
from __future__ import annotations

import subprocess
import sys
from datetime import datetime
from pathlib import Path

import pytest

from spectramaster import cli
from spectramaster.formats import get_format, load_all
from spectramaster.model import Spectrum

load_all()
ROOT = Path(__file__).resolve().parents[1]


def spec(n=256):
    return Spectrum(counts=[float(i % 17) for i in range(n)], energy_coeffs=[0.0, 0.5],
                    live_time=10.0, real_time=11.0, start_time=datetime(2020, 1, 2, 3, 4, 5),
                    sample_id="S1")


def write(path: Path, key="json"):
    path.parent.mkdir(parents=True, exist_ok=True)
    get_format(key).writer(spec(), path)
    return path


def test_formats_table(capsys):
    assert cli.main(["formats"]) == 0
    out = capsys.readouterr().out
    assert "ortec_chn" in out and "ci_cnf" in out and "Code" in out


def test_datamaster_syntax(tmp_path, capsys):
    src = write(tmp_path / "in file.json")
    dst = tmp_path / "out dir" / "Converted file.chn"
    assert cli.main(["-51", str(src), "-1", str(dst)]) == 0
    r = get_format("ortec_chn").reader(dst)[0]
    assert r.counts == spec().counts and r.sample_id == "S1"


def test_datamaster_auto_and_errors(tmp_path, capsys):
    src = write(tmp_path / "a.json")
    assert cli.main(["-0", str(src), "-7", str(tmp_path / "a.spe")]) == 0
    assert (tmp_path / "a.spe").exists()
    assert cli.main(["-99", str(src), "-1", str(tmp_path / "x.chn")]) == 2
    assert cli.main(["-51", str(tmp_path / "missing.json"), "-1", str(tmp_path / "x.chn")]) == 1
    assert cli.main(["-51", str(src), "-10", str(tmp_path / "x.phd")]) == 2  # PHD read-only
    assert cli.main(["-51", str(src)]) == 2


def test_convert_folder_recursive_keep_tree(tmp_path, capsys):
    inp = tmp_path / "in"
    write(inp / "a.json")
    write(inp / "sub" / "b.chn", "ortec_chn")
    (inp / "notes.md").write_text("ignore me")
    out = tmp_path / "out"
    rc = cli.main(["convert", str(inp), "--to", "spe", "--out", str(out), "-r", "--keep-tree"])
    text = capsys.readouterr().out
    assert rc == 0, text
    assert (out / "a_json.spe").exists()
    assert (out / "sub" / "b_chn.spe").exists()
    assert "2 converted" in text


def test_convert_non_recursive_and_from_filter(tmp_path, capsys):
    inp = tmp_path / "in"
    write(inp / "a.json")
    write(inp / "c.chn", "ortec_chn")
    write(inp / "sub" / "b.json")
    out = tmp_path / "out"
    assert cli.main(["convert", str(inp), "--to", "1", "--from", "json", "--out", str(out)]) == 0
    assert sorted(p.name for p in out.iterdir()) == ["a_json.chn"]


def test_convert_glob_and_failure_exit_code(tmp_path, capsys):
    write(tmp_path / "a.json")
    bad = tmp_path / "b.json"
    bad.write_text("{broken")
    rc = cli.main(["convert", str(tmp_path / "*.json"), "--to", "chn", "--from", "json"])
    text = capsys.readouterr().out
    assert rc == 1
    assert "FAILED" in text and "1 failed" in text
    assert (tmp_path / "a_json.chn").exists()


def test_no_overwrite(tmp_path, capsys):
    src = write(tmp_path / "a.json")
    assert cli.main(["convert", str(src), "--to", "chn"]) == 0
    assert cli.main(["convert", str(src), "--to", "chn", "--no-overwrite"]) == 1


def test_unknown_format_and_no_inputs(tmp_path, capsys):
    src = write(tmp_path / "a.json")
    assert cli.main(["convert", str(src), "--to", "nonsense"]) == 2
    assert cli.main(["convert", str(tmp_path / "nothing*.xyz"), "--to", "chn"]) == 1


def test_info(tmp_path, capsys):
    src = write(tmp_path / "طيف عربي.json")
    assert cli.main(["info", str(src)]) == 0
    out = capsys.readouterr().out
    assert "S1" in out and "Live time" in out and "256" in out
    assert cli.main(["info", str(tmp_path / "missing.chn")]) == 1


def test_gui_import_failure_is_graceful(monkeypatch, capsys):
    import builtins
    real_import = builtins.__import__

    def fake(name, *a, **k):
        if "gui" in name:
            raise ImportError("no Qt")
        return real_import(name, *a, **k)
    monkeypatch.setattr(builtins, "__import__", fake)
    assert cli.main([]) == 2
    assert "not available" in capsys.readouterr().err


def test_module_entry_point_arabic_path(tmp_path):
    src = write(tmp_path / "مجلد" / "عينة.json")
    dst = tmp_path / "مجلد" / "ناتج.chn"
    proc = subprocess.run([sys.executable, "-m", "spectramaster", "-51", str(src), "-1", str(dst)],
                          cwd=ROOT, capture_output=True)
    assert proc.returncode == 0, proc.stderr.decode("utf-8", "replace")
    assert dst.exists()
    assert "ناتج.chn" in proc.stdout.decode("utf-8")
