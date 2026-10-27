# Round-4 identification findings (after_R4B)

Protocol: `docs/baseline/round4_identify_protocol.md`. Synthetic spectra and the public CRM spectra of Zenodo 23093533 (counts and nuclide names only).

**6 PASS / 0 FAIL** (RB.C1-C6; RB.C7 is the test suite and the benchmark, reported in the protocol)

| ID | result | detail |
|---|---|---|
| RB.C1 | PASS | Codex's case 3.000000 keV (before 2.000000); FWHM cropped / full 1.116403/1.116403, 1.212884/1.212884, 1.430142/1.430142, 1.613107/1.613107, 1.774125/1.774125, 1.969628/1.969628; identification full {'Co-60': 1.0, 'Cs-137': 0.972, 'K-40': 0.948, 'Co-57': 0.744}, cropped {'Co-60': 0.974, 'Cs-137': 0.97, 'K-40': 0.931, 'Eu-152': 0.279} |
| RB.C2 | PASS | confidences {'none': {'K-40': 0.97, 'Cs-137': 0.966, 'Mo-99': 0.799, 'Tc-99m': 0.794, 'Mn-56': 0.779}, '1h': {'K-40': 0.97, 'Cs-137': 0.966, 'Mo-99': 0.799, 'Tc-99m': 0.794, 'Mn-56': 0.779}, '3d': {'K-40': 0.97, 'Cs-137': 0.966, 'Mo-99': 0.799, 'Tc-99m': 0.794}, '30d': {'K-40': 0.976, 'Cs-137': 0.973}}; date after start: ValueError: the sampling date is after the start of the acquisition |
| RB.C3 | PASS | Cs-137 0.973 (1 line(s)); K-40 0.964 (1 line(s)); Co-56 0.571 (1 line(s)) [note]; Ba-133 0.326 (1 line(s)) [note] |
| RB.C4 | PASS | all: Mo-99 0.80, Tc-99m 0.80, F-18 0.80, Ga-67 0.80, Ga-68 0.80, In-111 0.80, Tl-201 0.80, Lu-177 0.80, I-123 0.80, I-125 0.80, I-131 1.00, Cs-137 1.00; environmental: Mo-99 0.80, I-131 1.00, Cs-137 1.00; medical: Mo-99 1.00, Tc-99m 1.00, F-18 1.00, Ga-67 1.00, Ga-68 1.00, In-111 1.00, Tl-201 1.00, Lu-177 1.00, I-123 1.00, I-125 1.00, I-131 1.00 |
| RB.C5 | PASS | short-lived identifications 118 -> 0 with the date (limit 23.6); long-lived / series lost 3 of 3300 (limit 33.0) |
| RB.C6 | PASS | medical identifications 41 -> 21; long-lived / series lost 8 of 3303; short-lived without date 118 -> 108; single-line notes 293 |
