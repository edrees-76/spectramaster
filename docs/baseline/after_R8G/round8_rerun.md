# Round-8 re-runs of the round-7 harnesses (Codex M6, Gemini M2)

HEAD 3e75c89

| ID | value | result |
|---|---|---|
| RG8.C1 | every committed after_R7x file byte-identical after the --rerun runs | PASS |
| RG8.C2 | round7_tcs_refit at 1d610ac: 6 PASS / 0 FAIL; round7_combined at 0b95938: 5 PASS / 0 FAIL; round7_shared_background at 3cd2aa7: 4 PASS / 1 FAIL; round7_quad_limits at 27a54b1: 4 PASS / 0 FAIL; round7_inputs at 2469fda: 5 PASS / 0 FAIL | PASS |
| RG8.C3 | round7_tcs_refit at 3e75c89: 6 PASS / 0 FAIL; round7_combined at 3e75c89: 3 PASS / 2 FAIL (RB.C2 PASS -> FAIL from 3cd2aa7, RB.C5 PASS -> FAIL from 3cd2aa7); round7_shared_background at 3e75c89: 4 PASS / 1 FAIL; round7_quad_limits at 3e75c89: 4 PASS / 0 FAIL; round7_inputs at 3e75c89: 5 PASS / 0 FAIL | PASS |

Runs at the later merge commits:

- round7_combined at 3cd2aa7 (Merge pull request #95 from edrees-76/claude/r7c-shared-background): exit 1, RB.C1 PASS, RB.C2 FAIL, RB.C3 PASS, RB.C4 PASS, RB.C5 FAIL
