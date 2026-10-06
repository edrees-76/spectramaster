"""Walk test_corpus/, try SpectraMaster auto-detect + read on every data file,
and write catalog.csv (+ catalog_summary.txt).  Regenerate with:

    python test_corpus/build_catalog.py
"""
from __future__ import annotations

import csv
import sys
import time
import traceback
from collections import Counter, defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))

from spectramaster.convert import read_spectra  # noqa: E402
from spectramaster.formats import detect_format, load_all  # noqa: E402

SKIP_NAMES = {"SOURCES.md", "catalog.csv", "catalog_summary.txt", "expected.json",
              "build_catalog.py", "build_expected.py", "_manifest.json"}


def data_files():
    for p in sorted(HERE.rglob("*")):
        if not p.is_file() or p.name in SKIP_NAMES or p.name.startswith("_"):
            continue
        if p.name.upper() in ("INVENTORY.MD", "SAMPLE-URLS"):
            continue
        yield p


def magic(p: Path) -> str:
    b = p.read_bytes()[:16]
    txt = "".join(chr(c) if 32 <= c < 127 else "." for c in b)
    return b[:8].hex() + " |" + txt + "|"


def classify(exc: BaseException) -> str:
    msg = f"{type(exc).__name__}: {exc}"
    if "cannot recognise" in msg:
        return "not_detected"
    if "no spectrum found" in msg:
        return "empty"
    return type(exc).__name__


def main() -> None:
    load_all()
    rows = []
    for p in data_files():
        rel = p.relative_to(HERE).as_posix()
        row = {"path": rel, "source": rel.split("/")[0], "ext": p.suffix.lower() or "(none)",
               "size": p.stat().st_size, "magic": magic(p), "detected": "", "read_ok": False,
               "error_class": "", "error": "", "n_spectra": "", "channels": "", "total_counts": "",
               "live_time": "", "real_time": "", "calibrated": "", "seconds": ""}
        try:
            f = detect_format(p)
            row["detected"] = f.key if f else ""
        except Exception as exc:  # pragma: no cover
            row["detected"] = f"!{type(exc).__name__}"
        t0 = time.perf_counter()
        try:
            spectra, fmt = read_spectra(p)
            s = spectra[0]
            row.update(read_ok=True, n_spectra=len(spectra), channels=s.num_channels,
                       total_counts=round(s.total_counts, 6),
                       live_time=s.live_time if s.live_time is not None else "",
                       real_time=s.real_time if s.real_time is not None else "",
                       calibrated=bool(s.energy_coeffs))
        except Exception as exc:
            row["error_class"] = classify(exc)
            row["error"] = (f"{type(exc).__name__}: {exc}").replace("\n", " ")[:300]
            if row["error_class"] not in ("not_detected",):
                tb = traceback.extract_tb(exc.__traceback__)
                if tb:
                    last = tb[-1]
                    row["error"] += f" @ {Path(last.filename).name}:{last.lineno}"
        row["seconds"] = round(time.perf_counter() - t0, 3)
        rows.append(row)
        print(("OK  " if row["read_ok"] else "ERR ") + rel, row["detected"], row["error"][:100])

    with open(HERE / "catalog.csv", "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)

    # ---------------- summary
    out = []
    out.append(f"files: {len(rows)}  read OK: {sum(r['read_ok'] for r in rows)}")
    out.append("\nBy detected format:")
    byfmt = defaultdict(list)
    for r in rows:
        byfmt[r["detected"] or "(none)"].append(r)
    for k in sorted(byfmt):
        rs = byfmt[k]
        ok = sum(r["read_ok"] for r in rs)
        errs = Counter(r["error_class"] for r in rs if not r["read_ok"])
        out.append(f"  {k:20s} files={len(rs):4d} ok={ok:4d} fail={len(rs)-ok:4d} {dict(errs) if errs else ''}")
        for r in [r for r in rs if not r["read_ok"]][:4]:
            out.append(f"      e.g. {r['path']}  -> {r['error'][:160]}")
    out.append("\nUndetected files by extension (source):")
    und = defaultdict(Counter)
    for r in rows:
        if not r["detected"]:
            und[r["ext"]][r["source"]] += 1
    for ext, c in sorted(und.items()):
        out.append(f"  {ext:8s} {sum(c.values()):4d}  {dict(c)}")
    out.append("\nBy source:")
    bysrc = defaultdict(list)
    for r in rows:
        bysrc[r["source"]].append(r)
    for k, rs in sorted(bysrc.items()):
        out.append(f"  {k:10s} files={len(rs):4d} ok={sum(r['read_ok'] for r in rs):4d}")
    text = "\n".join(out)
    (HERE / "catalog_summary.txt").write_text(text, encoding="utf-8")
    print(text)


if __name__ == "__main__":
    main()
