# Round-8 limits of a nuclide whose primary result comes from another line (Codex H1 / Gemini H1)

engine 1.31.0

| ID | value | result |
|---|---|---|
| RA8.C1 | hpge_int_s0_key currie: threshold 2.876 -> 1.703 Bq, MDA 5.882 -> 3.553 Bq (key 1173.2 keV interfered 2.876 / 5.882; 1332.5 keV 1.703 / 3.553); hpge_int_s0_key iso11929: threshold 2.876 -> 1.703 Bq, MDA 8.236 -> 4.971 Bq (key 1173.2 keV interfered 2.876 / 8.236; 1332.5 keV 1.703 / 4.971); hpge_int_s0_mean currie: threshold 2.876 -> 1.703 Bq, MDA 5.882 -> 3.553 Bq (key 1173.2 keV interfered 2.876 / 5.882; 1332.5 keV 1.703 / 3.553); hpge_int_s0_mean iso11929: threshold 2.876 -> 1.703 Bq, MDA 8.236 -> 4.971 Bq (key 1173.2 keV interfered 2.876 / 8.236; 1332.5 keV 1.703 / 4.971); hpge_int_s1_key currie: threshold 2.884 -> 1.577 Bq, MDA 5.899 -> 3.302 Bq (key 1173.2 keV interfered 2.884 / 5.899; 1332.5 keV 1.577 / 3.302); hpge_int_s1_key iso11929: threshold 2.884 -> 1.577 Bq, MDA 8.26 -> 4.619 Bq (key 1173.2 keV interfered 2.884 / 8.26; 1332.5 keV 1.577 / 4.619); hpge_edge_key currie: threshold 8.734 -> 6.531 Bq, MDA 17.6 -> 13.21 Bq (key 1173.2 keV interfered 8.734 / 17.6; 1332.5 keV 6.531 / 13.21); hpge_edge_key iso11929: threshold 8.734 -> 6.531 Bq, MDA 24.64 -> 18.48 Bq (key 1173.2 keV interfered 8.734 / 24.64; 1332.5 keV 6.531 / 18.48) | PASS |
| RA8.C2 | before, the key line's limits: hpge_int_s0_key currie: 2.876 / 5.882 Bq; hpge_int_s0_key iso11929: 2.876 / 8.236 Bq; hpge_int_s0_mean currie: 2.876 / 5.882 Bq; hpge_int_s0_mean iso11929: 2.876 / 8.236 Bq; hpge_int_s1_key currie: 2.884 / 5.899 Bq; hpge_int_s1_key iso11929: 2.884 / 8.26 Bq; hpge_edge_key currie: 8.734 / 17.6 Bq; hpge_edge_key iso11929: 8.734 / 24.64 Bq | PASS |
| RA8.C3 | no usable line, as before: nai_curved_key currie: curved, 15.7 / 31.52 Bq; nai_curved_key iso11929: curved, 15.7 / 44.14 Bq | PASS |
| RA8.C4 | every line, every other nuclide field and the notes identical to before | PASS |
