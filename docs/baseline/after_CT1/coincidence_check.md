# Coincidence table: independent checks

Protocol: `docs/baseline/ensdf_coincidence_protocol.md`.

## Single-path cascades (P = 1 / (1 + alpha))

| Nuclide | i keV | j keV | table | expected | ok |
|---|---|---|---|---|---|
| Co-60 | 1173.228 | 1332.492 | 0.999838 | 0.999838 | True |
| Sc-48 | 1312.12 | 983.526 | 0.999876 | 0.999876 | True |
| Y-88 | 898.042 | 1836.063 | 0.99986 | 0.99986 | True |
| Eu-152 | 1408.006 | 121.7817 | 0.464037 | 0.464037 | True |

## Monte Carlo (200000 decays per mode, seed 12345)

237 pairs and annihilation probabilities compared, 0 outside max(0.005, 4 sigma); largest |table - simulation| 0.0242.

| Nuclide | mode | compared | failed | worst |
|---|---|---|---|---|
| Co-60 | B- | 1 | 0 | 0.0000 |
| Sc-48 | B- | 8 | 0 | 0.0001 |
| Y-88 | EC+B+ | 1 | 0 | 0.0000 |
| Na-22 | EC+B+ | 1 | 0 | 0.0005 |
| Cs-134 | B- | 12 | 0 | 0.0049 |
| Ba-133 | EC | 9 | 0 | 0.0097 |
| Eu-152 | B- | 12 | 0 | 0.0225 |
| Eu-152 | EC+B+ | 28 | 0 | 0.0242 |
| Bi-207 | EC+B+ | 2 | 0 | 0.0011 |
| Se-75 | EC | 5 | 0 | 0.0022 |
| Ir-192 | B- | 11 | 0 | 0.0059 |
| Ir-192 | EC | 9 | 0 | 0.0123 |
| Co-56 | EC+B+ | 29 | 0 | 0.0021 |
| Sb-124 | B- | 22 | 0 | 0.0115 |
| La-140 | B- | 11 | 0 | 0.0015 |
| Bi-214 | B- | 14 | 0 | 0.0048 |
| Pb-214 | B- | 2 | 0 | 0.0079 |
| Tl-208 | B- | 12 | 0 | 0.0079 |
| Ac-228 | B- | 47 | 0 | 0.0212 |
| Co-57 | EC | 1 | 0 | 0.0006 |

## Library coverage

Library gamma lines >= 1 % described: 1015; in the table but not described: 6 (In-114m 558.4, In-114m 725.2, Np-237 86.6, Sb-125 35.5, Te-131m 182.2, Zr-97 657.9).
Previous table: 975 described, 32 not described; lost: In-116m 1753.8, Kr-88 1249.0, Sb-126 1034.8, Sb-126 555.2, Sb-126 605.4.
No ENSDF data: Ag-109m, Ce-140m. Unresolved annihilation: none.
