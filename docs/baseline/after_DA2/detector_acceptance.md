# Detector acceptance test and chi-square counting test

Protocol: `docs/baseline/detector_acceptance_protocol.md`.

| ID | result | value |
|---|---|---|
| DA.C1 | PASS | largest |dev| FWHM 0.0180, FWTM 0.0178 |
| DA.C2 | PASS | largest |mean dev| FWHM 0.0174, FWTM 0.0175 |
| DA.C3 | PASS | largest |dev| 0.00000 |
| DA.C4 | PASS | mean z -0.038, |z| <= 2 0.950 (n 200) |
| DA.C5 | PASS | hand 214.421, engine 214.4212523719165 |
| DA.C6 | PASS | 10: [3.325, 16.919], 20: [10.117, 30.144] |
| DA.C7 | PASS | Poisson accepted 0.8980, extra scatter rejected 0.9950 |

## Measured

```
{
 "widths": {
  "rows": [
   {
    "gain": 0.5,
    "fwhm_true": 1.8,
    "fwtm_true": 3.280708311848991,
    "noiseless_fwhm": 1.8323811890738853,
    "noiseless_fwtm": 3.3389681408921206,
    "noiseless_fwhm_dev": 0.017989549485491807,
    "noiseless_fwtm_dev": 0.017758308116790467,
    "poisson_n": 50,
    "poisson_fwhm_dev": 0.017369366040725254,
    "poisson_fwtm_dev": 0.01752512587504773,
    "linear_crossings": 0
   },
   {
    "gain": 0.5,
    "fwhm_true": 2.2,
    "fwtm_true": 4.009754603370989,
    "noiseless_fwhm": 2.226438204068927,
    "noiseless_fwtm": 4.057508387392772,
    "noiseless_fwhm_dev": 0.01201736548587573,
    "noiseless_fwtm_dev": 0.011909403129467533,
    "poisson_n": 50,
    "poisson_fwhm_dev": 0.013082845852628422,
    "poisson_fwtm_dev": 0.012092892897390906,
    "linear_crossings": 0
   },
   {
    "gain": 0.25,
    "fwhm_true": 1.8,
    "fwtm_true": 3.280708311848991,
    "noiseless_fwhm": 1.8081081196769446,
    "noiseless_fwtm": 3.2953542970785747,
    "noiseless_fwhm_dev": 0.004504510931635952,
    "noiseless_fwtm_dev": 0.004464275344652435,
    "poisson_n": 50,
    "poisson_fwhm_dev": 0.0029142840261076053,
    "poisson_fwtm_dev": 0.004384319391889546,
    "linear_crossings": 0
   },
   {
    "gain": 0.25,
    "fwhm_true": 2.2,
    "fwtm_true": 4.009754603370989,
    "noiseless_fwhm": 2.206630079629349,
    "noiseless_fwtm": 4.0217419047064595,
    "noiseless_fwhm_dev": 0.003013672558794811,
    "noiseless_fwtm_dev": 0.002989534902059443,
    "poisson_n": 50,
    "poisson_fwhm_dev": 0.0037507358185453477,
    "poisson_fwtm_dev": 0.0036377937456688603,
    "linear_crossings": 0
   }
  ]
 },
 "efficiency": {
  "rows": [
   {
    "R": 20.0,
    "years": 5.0,
    "measured": 19.999999999000604,
    "dev": -4.9969806070748746e-11,
    "decay_factor": 0.5181481908584502
   },
   {
    "R": 20.0,
    "years": 0.0,
    "measured": 19.9999999990006,
    "dev": -4.997002811535367e-11,
    "decay_factor": 1.0
   },
   {
    "R": 40.0,
    "years": 5.0,
    "measured": 39.99999999800121,
    "dev": -4.9969806070748746e-11,
    "decay_factor": 0.5181481908584502
   },
   {
    "R": 40.0,
    "years": 0.0,
    "measured": 39.99999999800121,
    "dev": -4.9969806070748746e-11,
    "decay_factor": 1.0
   },
   {
    "R": 100.0,
    "years": 5.0,
    "measured": 99.99999999500301,
    "dev": -4.996991709305121e-11,
    "decay_factor": 0.5181481908584502
   },
   {
    "R": 100.0,
    "years": 0.0,
    "measured": 99.99999999500302,
    "dev": -4.9969806070748746e-11,
    "decay_factor": 1.0
   }
  ],
  "z_n": 200,
  "z_mean": -0.0375801793477141,
  "cov2": 0.95
 },
 "p_to_c": {
  "hand": 214.4212523719165,
  "engine": 214.4212523719165,
  "equal": true
 },
 "chi_square": {
  "points": {
   "10": [
    3.325,
    16.919
   ],
   "20": [
    10.117,
    30.144
   ]
  },
  "poisson_accepted": 0.898,
  "scatter_rejected": 0.995
 },
 "reported": {
  "fwhm_kev": 1.7946067976581617,
  "fwtm_kev": 3.278859883537052,
  "ratio": 1.8270631136668705,
  "p_to_c": 1527.379013761468,
  "model_fwhm_kev": 1.7697421281079344
 }
}
```
