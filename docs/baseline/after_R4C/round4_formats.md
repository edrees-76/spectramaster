# Round-4 format findings (after_R4C)

Protocol: `docs/baseline/round4_formats_protocol.md`. Synthetic files, the test corpus and the EML/Sanderson reference spectra (names, sums and flags only).

**4 PASS / 0 FAIL** (RC.C1-C4; RC.C5 is the test suite and the benchmark, reported in the protocol)

| ID | result | detail |
|---|---|---|
| RC.C1 | PASS | NaN: ValueError: the spectrum has 1 non-finite channel contents (NaN or infinity), channel 300: no peak search (before: returned 0); inf: ValueError: the spectrum has 1 non-finite channel contents (NaN or infinity), channel 300: no peak search; finite spectrum peaks [499.475193, 500.955039]; note '10 channels hold non-finite values (NaN or infinity): the spectrum can be viewed, but peak search and analysis refuse it' |
| RC.C2 | PASS | Gemini's case {'counts_0_4': [100, 500, 10, 20], 'live_time': 100.0, 'real_time': 100.0, 'time_channels': False, 'note': 'channel 0 equals the live time but channel 1 (500) is not a possible real time (0, or LT to 2 LT): channels 0 and 1 read as counts'} (before {'counts_0_4': [0, 0, 10, 20], 'live_time': 100.0, 'real_time': 500.0, 'time_channels': True, 'note': ''}); own IAEA .dat writer {'read_as': 'eml_sanderson', 'live_time': 1000.0, 'real_time': 1100.0, 'sum': 5110.0}; 38 EML/Sanderson files identical, 36 with time channels |
| RC.C3 | PASS | E = 1 keV x channel: warnings ['ORTEC ADCAM / MAESTRO (checked by reading the file back): the energy calibration 0 + 1 keV per channel is stored, but it is read back as the default of an uncalibrated MCA (no energy calibration)'] (before ['ORTEC ADCAM / MAESTRO (checked by reading the file back): energy calibration not stored']); 0.5 keV/ch unchanged |
| RC.C4 | PASS | SpecUtils TXT as .txt: ['specutils_txt', 1024, 15345.0, 100.0, 110.0] (before ['ascii2', 1024, 15345.0, None, None]); TKA as .xyz: ambiguous ['ascii1', 'tka'] (before content ['ascii1']); one-column file starting with zeros ascii1; other detection changes none; negative files detected 0 -> 0 |
