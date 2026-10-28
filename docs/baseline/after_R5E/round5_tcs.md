# Round-5 review, H5/H6: partial true-coincidence summing corrections

Protocol: `docs/baseline/round5_tcs_protocol.md`.

| ID | result | value |
|---|---|---|
| RE.C1 | PASS | Ba-133 356 keV, e_min 122: partial True, ignored 0.369959, factor 1.0000000, text 'partial true-coincidence summing correction: coincident photons below the efficiency curve left out (37 % of decays)'; e_min 50: partial False, factor 0.9703591 |
| RE.C2 | PASS | Ac-228 880.76: partial True, inconsistent 1.204864830514051, factor 1.0667626; Ac-228 338.32: partial True, inconsistent 0.11115207802417819, factor 0.9653405; Ac-228 911.204: partial False, inconsistent 5.755555222611117e-05, factor 0.9822991; Ac-228 968.971: partial False, inconsistent 5.8341994959702866e-05, factor 0.9829108; Ac-228 278.95: partial False, inconsistent 0.0, factor 0.8545400 |
| RE.C3 | PASS | 29228 line evaluations: correction changed for 0 []; partial 4646 of 29228 corrected |
| RE.C4 | FAIL | curve from 121.8 keV with Ba-133 points: calibration points of cascade emitters that the true-coincidence summing correction cannot treat: Ba-133 276.4 keV (partial true-coincidence summing correction: coincident photons below the efficiency curve left out (66 % of decays)); Ba-133 302.9 keV (partial true-coincidence summing correction: co (before: corrected); from 53.2 keV and Eu-152 only identical to before: False, True |
| RE.C5 | FAIL | e_min 122: activity 39.9433 +- 0.7707 Bq (before 39.9433), partial lines [356.013, 302.851, 383.849, 276.399], note 'true-coincidence summing corrected (COI 1.0000 at 356.013 keV); partial correction for 356.013, 302.851, 383.849, 276.399 keV'; e_min 50: partial lines [80.998] |
