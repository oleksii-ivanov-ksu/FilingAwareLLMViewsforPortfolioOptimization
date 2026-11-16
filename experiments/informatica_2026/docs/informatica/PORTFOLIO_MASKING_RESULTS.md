# Portfolio masking: completed results, 2026-11-16

Authorized new batch: 199 inputs × 2 conditions × 3 repetitions = 1,194
Grok 4.3 requests through OpenRouter/xAI. All valid, all generation IDs unique,
no retries; provider-reported cost $2.5373412 against the authorized $10 cap.
The previous 300-call pilot is separate. Validation confirms 801 frozen input
checksums, 997 source checksums, matching request payloads and unchanged sources.

| Slice | Mean-weight distance % | Average within % | Cross-minus-within pp | Fixed-support mean distance % |
|---|---:|---:|---:|---:|
| Core 2015 | 7.19 | 14.00 | -0.61 | 3.57 |
| Holdout 2015 | 9.52 | 13.77 | 0.22 | 4.07 |
| Core 2025 | 6.84 | 7.00 | 1.74 | 2.56 |
| Holdout 2025 | 12.47 | 16.16 | 1.40 | 5.01 |

Distances are half-L1, or one-way reallocated capital. Mean-weight distance
compares means of three weight vectors, not weights from mean views. Within
averages the three original and three masked pair distances. Cross averages
nine dependent cross-condition pairs. Four slices cover two dates and two
stock groups, not four independent population experiments.

Interpretation: the mean original/masked weights differ materially, but repeat
variability is large. Cross-minus-within is not positive in every slice. The
whole mean-weight difference cannot be assigned to identity removal; no
population significance or equivalence is established. Fixed historical
support/uncertainty gives smaller distances, but it differs from new-model
selection and cannot identify the fraction caused by filtering. Names/tickers
were removed; other identity clues, fixed extracted facts and financial context
remain. This is not decontamination and produces no new return backtest.

Author-facing contribution: evaluate the stability of the full view-to-weight
interface, not only correlations or shifts in views. Combined with matched
controls, the evidence supports a conditional computational audit rather than
an established profitable forecasting method.

Artifacts: data/v2/analysis/informatica_revision/portfolio_masking_grok43_v1/
contains frozen runner/protocol, responses, analysis.json, targets.json,
response_hashes.json, analysis_self_check.json and final_validation.json.
Offline replication verifies distances from saved weights. Full inference and
licensed raw-data regeneration are outside the public-candidate scope.
