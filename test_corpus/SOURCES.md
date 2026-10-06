# SpectraMaster real-world test corpus

Downloaded 2026-10-05: data files only, fetched from `raw.githubusercontent.com` at pinned commits.
Original repository paths are kept under `test_corpus/<source>/`. No code from these projects
was run or installed. `_manifest.json` lists every file. Each folder's `_LICENSE*`/`_COPYING` is the
upstream license file. Total size is about 24 MB (283 data files).

| Folder | Upstream | Commit (date) | License | Files / size | What's inside |
|---|---|---|---|---|---|
| SpecUtils | https://github.com/sandialabs/SpecUtils | 1fa561f3 (2026-10-05) | LGPL-2.1 | 1 / 0.05 MB | `unit_tests/test_data/spectra/Mn56_DetX_Shielded.n42` (N42-2012) |
| InterSpec | https://github.com/sandialabs/InterSpec | 24307caa (2026-10-05) | LGPL-2.1 | 114 / 11.6 MB | `example_spectra/*.n42`; `target/testing/**` N42/PCF/CNF analysis test inputs; fuzz seeds `target/fuzzing/corpus/state_xml`; 55 `data/reference_spectra/Common_Field_Nuclides/<detector>/{Am241,Ba133,Co60,Cs137,Eu152}_Unshielded.txt` (`RADDATA://` URI-encoded spectra, 11 detector models) |
| becquerel | https://github.com/lbl-anp/becquerel | c8ef15ad (2026-07-29) | BSD-3-Clause-LBNL | 19 / 1.0 MB | `tests/samples` (CNF, ORTEC SPE/SPC, IEC 1455, becquerel HDF5) + `tests/samples_converted` (becquerel's own SPE exports of the CNF/SPC). Skipped: `tests/samples/misc/cllbc_listmode.h5` (25 MB list-mode HDF5) |
| xylib | https://github.com/wojdyr/xylib | 199a1eda (2022-08-07) | LGPL-2.1 | 8 / 0.34 MB | `samples/*.CNF` (2), `*.mca` (2, Canberra), `1d-*.spe` (3, Princeton WinSpec, not gamma), `sample-urls` |
| pyne | https://github.com/pyne/pyne | e52190ae (2026-09-03) | BSD-style (GitHub: NOASSERTION; license file not fetched) | 2 / 0.04 MB | `tests/gv_format_spect.spe` (IAEA $ SPE), `tests/test.spe` (ORTEC "ACQUISITION INFORMATION" text report) |
| curie | https://github.com/jtmorrell/curie | 261832fb (2026-08-15) | MIT | 1 / 0.15 MB | `examples/eu_calib_7cm.Spe` |
| BecqMoni | https://github.com/Am6er/BecqMoni | f4abe6c8 (2026-10-05) | GPL-2.0 | 59 / 8.5 MB | 37 N42 importer edge cases `handover/g6-a253/cases/*.n42` (2006/2012/`RadiologicalInstrumentData` variants, bad dates, NaN and so on); 22 BecqMoni/RadiaCode `ResultDataFile` XML spectra (`tools/CORPUS/corpus/{spectra,pinned}`, `tools/fsa_showcase/spectra`) |
| RASE | https://github.com/llnl/RASE | 7f8e0741 (2026-03-23) | MIT / LGPL-2.1 (dual) | 31 / 0.4 MB | `baseSpectra/**.n42`, `tests/**.n42` (N42-2012, multi-secondary). The 47 `n42Templates/*` files were removed after download: they are Mako templates with `${...}` placeholders, not spectra |
| muGPD | https://github.com/augustocattafesta/muGPD | 2e73ab05 (2026-05-17) | GPL-3.0 | 8 / 0.02 MB | Amptek `<<PMCA SPECTRUM>>` .mca, one per data folder |
| MBFS | https://github.com/LAHCEN-EL-AMRI/MBFS | cbfbd93b (2025-02-10) | AGPL-3.0 | 38 / 1.7 MB | `MBFS/Converter/example`: lab ORTEC CHN/SPC/SPE (some of the same measurement in several formats) plus the converter's `Converter_*` outputs |
| hdtv | https://github.com/hdtv-tool/hdtv | f01a1c04 (2026-04-08) | GPL-2.0 (per GitHub; license file not fetched) | 5 / 0.03 MB | hdtv/mfile `.spc` test spectra and `spec-samples/1k.txt` |

Candidates checked and not used: Burucs99/gamma-spectroscopy-analysis (Amptek MCA, no license),
tegmyr/ortec_read (no license; the same 17_1113_3A.Spe is in MBFS), Kruszk TKA files (no license),
silx-kit/pymca (XRF, not gamma), MaksVasilev/BecqMoniResources and ssesselmann/impulse (no sample spectra).
We found no public IAEA or NIST repository with directly downloadable sample files.

## Generated files
* `catalog.csv`, `catalog_summary.txt`: `python test_corpus/build_catalog.py`. For every file this records the
  extension, size, magic bytes, detected format, whether the read succeeded, the error, channels, total counts and live/real time.
* `expected.json`: `python test_corpus/build_expected.py`. Holds reference values that are independent of our
  readers: source-project unit-test asserts, plain-text headers, and the same measurement in another format.
* `tests/test_corpus.py` uses both files.
