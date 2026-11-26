# Filing-summary ablation: complete descriptive results

199 cases, 1,791 valid responses, 1,791 unique generation IDs, no retries. Cost USD 3.75638290; authorized cap USD 10.

## View-level contrasts

All 199 cases, three responses per condition. Differences are A minus B.

| A / B | Signed mean bps | Absolute mean difference bps | Within A / B bps | Cross bps | Cross minus within bps | Sign changes |
|---|---:|---:|---:|---:|---:|---:|
| Real / No text | -0.37 | 26.88 | 13.97 / 12.46 | 29.40 | 16.18 | 43/199 |
| Real / Shuffled | 7.99 | 36.88 | 13.97 / 16.28 | 39.11 | 23.98 | 47/199 |
| Shuffled / No text | -8.36 | 28.21 | 16.28 / 12.46 | 30.89 | 16.52 | 41/199 |

These are descriptive case averages, not independent market experiments or forecast errors. Sign changes include transitions to/from zero.

## Portfolio-weight contrasts

Primary allocation: positive medium-confidence views, fixed neutral sentiment, same prior/covariance/tilt. Distances are half-L1, expressed as percent of capital. Excess is in percentage points.

| Slice | A / B | Mean-vector distance % | Within A / B % | Cross % | Excess pp |
|---|---|---:|---:|---:|---:|
| core 2015 | Real / No text | 16.19 | 17.29 / 9.25 | 20.09 | 6.82 |
| core 2015 | Real / Shuffled | 23.08 | 17.29 / 8.09 | 26.23 | 13.54 |
| core 2015 | Shuffled / No text | 16.51 | 8.09 / 9.25 | 17.80 | 9.13 |
| holdout 2015 | Real / No text | 20.20 | 14.41 / 9.49 | 22.81 | 10.86 |
| holdout 2015 | Real / Shuffled | 21.39 | 14.41 / 17.59 | 26.07 | 10.06 |
| holdout 2015 | Shuffled / No text | 18.99 | 17.59 / 9.49 | 22.69 | 9.14 |
| core 2025 | Real / No text | 12.46 | 9.15 / 11.81 | 15.47 | 4.99 |
| core 2025 | Real / Shuffled | 10.82 | 9.15 / 4.89 | 12.43 | 5.41 |
| core 2025 | Shuffled / No text | 9.08 | 4.89 / 11.81 | 11.46 | 3.11 |
| holdout 2025 | Real / No text | 13.83 | 16.71 / 11.23 | 17.94 | 3.96 |
| holdout 2025 | Real / Shuffled | 14.57 | 16.71 / 8.50 | 18.59 | 5.98 |
| holdout 2025 | Shuffled / No text | 14.59 | 8.50 / 11.23 | 16.00 | 6.13 |

## Confidence and accepted views

| Condition | High | Medium | Low |
|---|---:|---:|---:|
| Real | 1 | 509 | 87 |
| No text | 0 | 357 | 240 |
| Shuffled | 1 | 498 | 98 |

| Slice | Condition | Accepted across three repeats |
|---|---|---|
| core 2015 | Real | 10, 14, 12 |
| core 2015 | No text | 6, 10, 6 |
| core 2015 | Shuffled | 7, 10, 9 |
| holdout 2015 | Real | 18, 19, 17 |
| holdout 2015 | No text | 17, 15, 14 |
| holdout 2015 | Shuffled | 16, 19, 17 |
| core 2025 | Real | 21, 21, 21 |
| core 2025 | No text | 12, 15, 12 |
| core 2025 | Shuffled | 14, 12, 14 |
| holdout 2025 | Real | 16, 19, 22 |
| holdout 2025 | No text | 21, 20, 17 |
| holdout 2025 | Shuffled | 16, 15, 15 |

## Fixed-support diagnostic

All available cases enter with sigma 0.03 regardless of confidence/sign. This is a sensitivity diagnostic, not BL-Filing+.

| Slice | A / B | Mean-vector distance % | Cross minus within pp |
|---|---|---:|---:|
| core 2015 | Real / No text | 17.52 | 11.52 |
| core 2015 | Real / Shuffled | 25.12 | 17.50 |
| core 2015 | Shuffled / No text | 17.23 | 10.07 |
| holdout 2015 | Real / No text | 16.34 | 9.99 |
| holdout 2015 | Real / Shuffled | 22.16 | 15.04 |
| holdout 2015 | Shuffled / No text | 13.34 | 7.45 |
| core 2025 | Real / No text | 12.07 | 8.06 |
| core 2025 | Real / Shuffled | 17.23 | 11.54 |
| core 2025 | Shuffled / No text | 15.80 | 10.77 |
| holdout 2025 | Real / No text | 15.48 | 9.28 |
| holdout 2025 | Real / Shuffled | 19.00 | 12.70 |
| holdout 2025 | Shuffled / No text | 15.70 | 10.24 |

## Scope and validation

Financial context and recipient headers are identical across conditions. The intervention concerns complete saved filing-summary blocks, including their narrative numbers and sentiment; it is not raw-filings extraction. One fixed donor permutation within each date/group is used across all repeats. Donor sectors and identity clues may differ. No historical sentiment enters the allocation through Omega.

Sensitivity does not establish information quality, useful forecasts or profitable allocations. Four dependent slices and one donor permutation cannot establish a population effect. No new return backtest, p-value search, temporal decontamination or historical-universe repair is claimed. Prior real-text responses are not pooled with this experiment.

Independent validation: 1796 input files, 1198 source files, all request payloads, 24 weight contrasts and 15 view contrasts. Source files unchanged.

Artifacts: data/v2/analysis/informatica_revision/text_ablation_grok43_v1/{analysis.json,targets.json,response_hashes.json,final_validation.json}; frozen protocol and inputs are retained separately. The current article is not automatically rewritten from this pilot.

## Interpretation for the revision

1. Saved filing summaries affect the second-stage outputs beyond the fixed
   numerical context. Real/no-text mean absolute view difference is 26.88 bps;
   real/shuffled is 36.88 bps. Their cross-minus-within distances are 16.18 and
   23.98 bps. The signed real/no-text average is only −0.37 bps: positive and
   negative company-specific changes largely cancel, so the signed average
   alone would conceal sensitivity.
2. In all four slices, the primary cross-condition weight distance exceeds
   average within-condition distance for real/no-text and real/shuffled. The
   corresponding mean-vector distances are 12.46–20.20% and 10.82–23.08% of
   capital. These are descriptive contrasts, not population significance tests.
3. Numerical sensitivity also persists on common all-case support with fixed
   uncertainty. Thus sensitivity is observable without changing the confidence
   filter; this is not a quantitative causal decomposition of the primary weights.
4. Medium-confidence labels occur in 85.26% of real-text responses, 59.80%
   without text and 83.42% with shuffled text. Presence of mismatched text also
   accompanies higher reported confidence. These labels are not calibrated
   probabilities, and correctness was not measured. Do not equate confidence
   increases with more useful information.
5. All 199 donors share the recipient fiscal-period label; only 33 share its
   sector. The other 166 mismatched bundles can introduce sector/identity conflict.
   The single permutation cannot separate these mechanisms.

This adds a controlled content-ablation result to the evidence about the
view-to-weight interface. It does not establish that the correct text improves
forecast accuracy, Sharpe, or deployment outcomes. It therefore supports a
stronger diagnostic account, not reinstatement of the rejected alpha claim.
A larger paid run is not automatically justified by sensitivity alone; define
a temporally valid usefulness endpoint before scaling.
