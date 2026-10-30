# Round-8 re-runs of the round-7 harnesses (Codex M6, Gemini M2)

HEAD 5de3b03

| ID | value | result |
|---|---|---|
| RG8.C1 | every committed after_R7x file byte-identical after the --rerun runs | PASS |
| RG8.C2 | round7_tcs_refit at 1d610ac: 6 PASS / 0 FAIL; round7_combined at 0b95938: 5 PASS / 0 FAIL; round7_shared_background at 3cd2aa7: 4 PASS / 1 FAIL; round7_quad_limits at 27a54b1: 4 PASS / 0 FAIL; round7_inputs at 2469fda: 5 PASS / 0 FAIL | PASS |
| RG8.C3 | round7_tcs_refit at 5de3b03: 6 PASS / 0 FAIL; round7_combined at 5de3b03: 2 PASS / 3 FAIL (RB.C2 PASS -> FAIL from 3cd2aa7, RB.C3 PASS -> FAIL from 5de3b03, RB.C5 PASS -> FAIL from 3cd2aa7); round7_shared_background at 5de3b03: 4 PASS / 1 FAIL; round7_quad_limits at 5de3b03: 2 PASS / 2 FAIL (RD.C2 PASS -> FAIL from 5de3b03, RD.C3 PASS -> FAIL from 5de3b03); round7_inputs at 5de3b03: 5 PASS / 0 FAIL | PASS |

Runs at the later merge commits:

- round7_combined at 3cd2aa7 (Merge pull request #95 from edrees-76/claude/r7c-shared-background): exit 1, RB.C1 PASS, RB.C2 FAIL, RB.C3 PASS, RB.C4 PASS, RB.C5 FAIL
- round7_combined at 27a54b1 (Merge pull request #96 from edrees-76/claude/r7d-quad-limits): exit 1, RB.C1 PASS, RB.C2 FAIL, RB.C3 PASS, RB.C4 PASS, RB.C5 FAIL
- round7_combined at 2469fda (Merge pull request #97 from edrees-76/claude/r7e-inputs): exit 1, RB.C1 PASS, RB.C2 FAIL, RB.C3 PASS, RB.C4 PASS, RB.C5 FAIL
- round7_combined at c942377 (Merge pull request #98 from edrees-76/claude/r7f-warnings-threads): exit 1, RB.C1 PASS, RB.C2 FAIL, RB.C3 PASS, RB.C4 PASS, RB.C5 FAIL
- round7_combined at 384e89d (Merge pull request #99 from edrees-76/claude/r7g-tests): exit 1, RB.C1 PASS, RB.C2 FAIL, RB.C3 PASS, RB.C4 PASS, RB.C5 FAIL
- round7_combined at 497467b (Merge pull request #100 from edrees-76/claude/r8a-alt-limits): exit 1, RB.C1 PASS, RB.C2 FAIL, RB.C3 PASS, RB.C4 PASS, RB.C5 FAIL
- round7_combined at a68c114 (Merge pull request #101 from edrees-76/claude/r8f-scan-cancel): exit 1, RB.C1 PASS, RB.C2 FAIL, RB.C3 PASS, RB.C4 PASS, RB.C5 FAIL
- round7_combined at 68721ca (Merge pull request #102 from edrees-76/claude/r8e-inputs): exit 1, RB.C1 PASS, RB.C2 FAIL, RB.C3 PASS, RB.C4 PASS, RB.C5 FAIL
- round7_combined at 6ba72d7 (Merge pull request #103 from edrees-76/claude/r8d-spe-truncation): exit 1, RB.C1 PASS, RB.C2 FAIL, RB.C3 PASS, RB.C4 PASS, RB.C5 FAIL
- round7_combined at dbfb5b5 (Merge pull request #104 from edrees-76/claude/r8b-peak-mode): exit 1, RB.C1 PASS, RB.C2 FAIL, RB.C3 PASS, RB.C4 PASS, RB.C5 FAIL
- round7_combined at 77310c2 (Merge pull request #105 from edrees-76/claude/r8c-coi-guard): exit 1, RB.C1 PASS, RB.C2 FAIL, RB.C3 PASS, RB.C4 PASS, RB.C5 FAIL
- round7_combined at 09d5efe (Merge pull request #106 from edrees-76/claude/r8g-harness-rerun): exit 1, RB.C1 PASS, RB.C2 FAIL, RB.C3 PASS, RB.C4 PASS, RB.C5 FAIL
- round7_combined at 5de3b03 (Merge pull request #107 from edrees-76/claude/r8h-line-covariance): exit 1, RB.C1 PASS, RB.C2 FAIL, RB.C3 FAIL, RB.C4 PASS, RB.C5 FAIL
- round7_quad_limits at 2469fda (Merge pull request #97 from edrees-76/claude/r7e-inputs): exit 0, RD.C1 PASS, RD.C2 PASS, RD.C3 PASS, RD.C4 PASS
- round7_quad_limits at c942377 (Merge pull request #98 from edrees-76/claude/r7f-warnings-threads): exit 0, RD.C1 PASS, RD.C2 PASS, RD.C3 PASS, RD.C4 PASS
- round7_quad_limits at 384e89d (Merge pull request #99 from edrees-76/claude/r7g-tests): exit 0, RD.C1 PASS, RD.C2 PASS, RD.C3 PASS, RD.C4 PASS
- round7_quad_limits at 497467b (Merge pull request #100 from edrees-76/claude/r8a-alt-limits): exit 0, RD.C1 PASS, RD.C2 PASS, RD.C3 PASS, RD.C4 PASS
- round7_quad_limits at a68c114 (Merge pull request #101 from edrees-76/claude/r8f-scan-cancel): exit 0, RD.C1 PASS, RD.C2 PASS, RD.C3 PASS, RD.C4 PASS
- round7_quad_limits at 68721ca (Merge pull request #102 from edrees-76/claude/r8e-inputs): exit 0, RD.C1 PASS, RD.C2 PASS, RD.C3 PASS, RD.C4 PASS
- round7_quad_limits at 6ba72d7 (Merge pull request #103 from edrees-76/claude/r8d-spe-truncation): exit 0, RD.C1 PASS, RD.C2 PASS, RD.C3 PASS, RD.C4 PASS
- round7_quad_limits at dbfb5b5 (Merge pull request #104 from edrees-76/claude/r8b-peak-mode): exit 0, RD.C1 PASS, RD.C2 PASS, RD.C3 PASS, RD.C4 PASS
- round7_quad_limits at 77310c2 (Merge pull request #105 from edrees-76/claude/r8c-coi-guard): exit 0, RD.C1 PASS, RD.C2 PASS, RD.C3 PASS, RD.C4 PASS
- round7_quad_limits at 09d5efe (Merge pull request #106 from edrees-76/claude/r8g-harness-rerun): exit 0, RD.C1 PASS, RD.C2 PASS, RD.C3 PASS, RD.C4 PASS
- round7_quad_limits at 5de3b03 (Merge pull request #107 from edrees-76/claude/r8h-line-covariance): exit 1, RD.C1 PASS, RD.C2 FAIL, RD.C3 FAIL, RD.C4 PASS
