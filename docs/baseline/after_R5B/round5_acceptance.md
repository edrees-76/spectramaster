# Round-5 review: detector acceptance test and activity entry

Protocol: `docs/baseline/round5_acceptance_protocol.md`.

| ID | result | value |
|---|---|---|
| RB.C1 | PASS | largest relative difference cut / full 9.63e-10 |
| RB.C2 | PASS | largest relative difference full / before 0; DA.C1-C7 equal to after_DA2: True |
| RB.C3 | PASS | from 1060 keV: None; from 1030 keV: 235.64978197988242 (full 235.64978197988242) |
| RB.C4 | PASS | 8 of 8 QC texts as registered |
| RB.C5 | PASS | refused 5 of 5, read 5 of 5, relative efficiency refuses 3 of 3 |
| RB.C6 | PASS | round trip [12345.678, 246.91356], edited 2000.0 Bq |

## Measured

```
{
 "C1_C2": {
  "linear": {
   "full": [
    1332.5,
    2.0290541514755205,
    3.697680701578065,
    1.8223666918347772,
    235.64978197988242
   ],
   "cut": [
    1332.5,
    2.0290541496701735,
    3.6976807016257,
    1.8223666934797007,
    235.64978197988242
   ],
   "before": [
    1332.5,
    2.0290541514755205,
    3.697680701578065,
    1.8223666918347772,
    235.64978197988242
   ],
   "cut_vs_full": 9.026304148562758e-10,
   "full_vs_before": 0.0
  },
  "quadratic": {
   "full": [
    1332.5130274007079,
    2.0611789609121796,
    3.730729825747318,
    1.809998013998879,
    286.6314956682205
   ],
   "cut": [
    1332.5130274007074,
    2.0611789616999943,
    3.7307298235797752,
    1.8099980122554662,
    286.6314956682205
   ],
   "before": [
    1332.5130274007079,
    2.0611789609121796,
    3.730729825747318,
    1.809998013998879,
    286.6314956682205
   ],
   "cut_vs_full": 9.63212509752509e-10,
   "full_vs_before": 0.0
  }
 },
 "DA2": {
  "equal": true
 },
 "C3": {
  "1060.0": {
   "p_to_c": null,
   "notes": [
    "the 1040-1096 keV Compton window is not fully inside the spectrum: no peak-to-Compton ratio"
   ],
   "full": 235.64978197988242
  },
  "1030.0": {
   "p_to_c": 235.64978197988242,
   "notes": [],
   "full": 235.64978197988242
  }
 },
 "C4_C5": {
  "qc": [
   {
    "text": "Cs-137=37000",
    "expected": {
     "Cs-137": 37000.0
    },
    "got": {
     "Cs-137": 37000.0
    }
   },
   {
    "text": "Cs-137=37000, Co-60=1 uCi",
    "expected": {
     "Cs-137": 37000.0,
     "Co-60": 37000.0
    },
    "got": {
     "Cs-137": 37000.0,
     "Co-60": 37000.0
    }
   },
   {
    "text": "Cs-137=1 µCi; Co-60=2 kBq",
    "expected": {
     "Cs-137": 37000.0,
     "Co-60": 2000.0
    },
    "got": {
     "Cs-137": 37000.0,
     "Co-60": 2000.0
    }
   },
   {
    "text": "Cs-137=1,000 Bq",
    "expected": null,
    "got": null
   },
   {
    "text": "Cs-137=1,5 Bq",
    "expected": null,
    "got": null
   },
   {
    "text": "Cs-137=1e309",
    "expected": null,
    "got": null
   },
   {
    "text": "Cs-137=abc",
    "expected": null,
    "got": null
   },
   {
    "text": "Cs-137",
    "expected": null,
    "got": null
   }
  ],
  "refused": {
   "1,000": null,
   "1,5 Bq": null,
   "1e309": null,
   "nan": null,
   "inf": null
  },
  "read": [
   {
    "text": "37 kBq",
    "expected": 37000.0,
    "got": 37000.0
   },
   {
    "text": "1uCi",
    "expected": 37000.0,
    "got": 37000.0
   },
   {
    "text": "1 µCi",
    "expected": 37000.0,
    "got": 37000.0
   },
   {
    "text": ".5e3",
    "expected": 500.0,
    "got": 500.0
   },
   {
    "text": "-2 Bq",
    "expected": -2.0,
    "got": -2.0
   }
  ],
  "relative_efficiency_raises": {
   "inf activity": true,
   "nan activity": true,
   "inf live time": true
  }
 },
 "C6": {
  "round_trip": [
   12345.678,
   246.91356
  ],
  "edited_bq": 2000.0
 }
}
```
