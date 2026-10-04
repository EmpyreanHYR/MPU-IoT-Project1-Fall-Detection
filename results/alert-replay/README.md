# Fixed-rule alert replay

`summary.json` replays the deployed confirmation rules on the 12 primary
MaskedBiMamba test sequences. The rules were not fitted or tuned by this analysis.

- Confirmed-event recall: 0.7752 ± 0.0958.
- Unmatched confirmed alerts per evaluated video hour: 66.7 ± 45.2.
- Confirmation offset from merged positive-window start: 1.88 ± 0.28 s.

Reference events merge positive target windows. Exposure includes retained fall
and non-fall video segments. The rates are descriptive test-segment quantities,
not continuous-care notification rates. Raw predicted events and confirmed
alerts must be reported separately.
