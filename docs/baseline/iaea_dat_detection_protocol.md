# IAEA ASCII .dat output read as EML Sanderson: pre-registered protocol

Written 2026-10-22, before implementation. This is the separate finding recorded in
`any_extension_protocol.md`: our IAEA ASCII `.dat` output (code 65) is detected as EML Sanderson
(code 17). Results are appended below the line after the run; nothing above it changes after its
SHA-256 is recorded.

## 1. What the files are

Measured before writing this protocol, from the 38 EML `.DAT` reference files and the code.
These measurements were made read-only; the files are not copied into the repository.

* **The layout is the same.**
  * Our writer (`write_iaea_dat`) writes the EML layout: a header with `LT=` and `ST=`, then rows
    of 10 fixed-width integers (width 7, or wider for large values).
  * It stores the live time in channel 0 and the real time in channel 1.
  * The EML files use the same convention. In 36 of the 38 files the header `LT=` equals
    channel 0 (for example TEST01: `LT=240000`, channel 0 = 240000). The exceptions are BKG.DAT
    (channel 0 = 0) and CALIBR01.DAT (no `LT=`).
  * The content of our output therefore cannot be told apart from an EML file.
* **The two readers differ in meaning, not in layout.**
  * `read_iaea_dat` splits rows on spaces. It takes channels 0 and 1 as live and real time and
    sets them to 0.
  * `read_sanderson` reads fixed-width fields. It keeps channels 0 and 1 as counts and sets
    real time = live time.
  * TEST01.DAT has a row whose fields touch. The fixed-width reader reads it correctly; splitting
    on spaces would shift the channels. So the fixed-width reader is the right one for this layout.
* **Current behaviour.**
  * Under `.dat` the usual stage tries Sanderson (code 17) first. Our output is read with the
    times as counts in channels 0 and 1, and its real time is lost.
  * Under another extension, the content stage prefers `iaea_ascii_dat` (`CONTENT_PREFERENCE`).
    So the same EML file is read by a different reader depending on its name.
* **Prototype, outside the repository.** Setting channels 0 and 1 to 0 in the Sanderson reader when
  header `LT=` equals channel 0 changes no value of the benchmark's EML reference results.

## 2. Change

1. **`read_sanderson`.** When the header has `LT=` and channel 0 equals that live time, channels
   0 and 1 are the live and real time, as in `read_iaea_dat`:
   * real time = max(channel 1, live time);
   * both channels are set to 0;
   * `extra["time_channels"] = True`.

   Otherwise the read is unchanged.
2. **`CONTENT_PREFERENCE`.** The pair becomes (`eml_sanderson`, `iaea_ascii_dat`). With any name, a
   file that both content tests accept is read by the fixed-width reader, as under `.dat`.
3. **Unchanged:**
   * the writer;
   * the usual detection order;
   * the format label: such files are still reported as `eml_sanderson`, because their content is
     identical;
   * `read_iaea_dat` (still used when chosen by hand, and for files only it accepts, such as rows
     wider than 80 characters);
   * engine and limits; `ENGINE_VERSION` stays 1.9.0.

## 3. Criteria (set before the run)

| id | what | limit |
|---|---|---|
| ID.C1 | Round trip of our output. Spectra: the 512-channel `_spec()` of `tests/test_aptec_import_ascii.py`; synthetic HPGe (4096 channels) and NaI (1024 channels); a spectrum with largest value >= 1e6 (field width 8); one with >= 1e7 (width 9). Each has a start time and real time != live time. Each is written with `write_iaea_dat` as `x.dat`, `x.xyz` and `x`, then read with automatic detection | counts, live time, real time, sample id and start time identical to `read_iaea_dat` of the same file: 0 differences |
| ID.C2a | The 38 EML `.DAT` files, under their own name and as a `.xyz` copy in a temporary folder | same format under both names, identical read: 0 differences |
| ID.C2b | The same files read now against `main` | counts identical except channels 0 and 1 of the files with header `LT=` equal to channel 0, which are 0. Live time, sample id and start time identical. Real time = max(channel 1, live time) for those files, unchanged for the others |
| ID.C3 | Standard benchmark, compared with after_TO2 (values and key order) | identical except runtime fields (as in `benchmark_tie_order_amendment_protocol.md` §3); 154 PASS / 13 FAIL / 60 REPORT |
| ID.C4 | New unit tests | pass |
| ID.C5 | Full test suite | passes; changed existing tests listed with reasons |

**Reported, not criteria:**
* the number of EML files with time channels (expected 36);
* the detected format of each ID.C1 case;
* the `any_extension` harness rows that change against after_AX1.

Outputs go to a new folder `docs/baseline/after_ID1/`.

---
## Results

(appended after the run)
