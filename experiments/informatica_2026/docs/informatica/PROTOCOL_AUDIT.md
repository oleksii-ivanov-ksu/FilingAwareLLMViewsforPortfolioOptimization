# Protocol audit closure — 2026-11-16

This audit distinguishes resolved reporting errors from properties of the data
that cannot be repaired by editing the article. It does not authorize a new
corpus run or replace the frozen experiment.

| Question | Evidence | Disposition |
|---|---|---|
| Source manuscript | Google Docs export dated 2026-11-16; frozen CE PDF 21 pages | Normalized word similarity 0.9942. The 31 differences are section/figure numbering and math omitted by text extraction; no substantive prose replacement identified. Both have the template residue and duplicate related-work heading. New draft removes them. |
| Universe selection | config/universe.yaml metadata | Recorded selection date 2026-01-23; 50 Core and 50 Holdout; complete filing-link/estimate history and sector coverage are stated selection criteria. This is after the return sample, not historical membership reconstruction. Metadata is evidence of the recorded selection, not independent verification of completeness. |
| Estimate vintages | 100 analyst_estimates.json files, 9,465 records | Fields contain fiscal-period dates but no independent observation/revision timestamp. _find_matching_estimate matches a period within five days. Historical availability cannot be certified. |
| Price context | InputBuilder/_calculate_price_metrics | Price dates filtered to <= as_of_date; 21/63-day returns and 60-day annualized volatility. Same-date inclusion and retrieved adjusted history are not an intraday/vintage availability guarantee. |
| Model outputs | ViewReasoner/generate_view | Historical parser clamps integer views to bounds and substitutes defaults for invalid confidence/short explanations. This differs from strict no-repair validation in the new pilot; do not equate their validity rates. |
| Return reporting | frozen core/holdout daily returns | Removed 13 2026 observations per split only in the new analysis. Replaced CAGR-ratio label with arithmetic Sharpe; separated mean tests and Sharpe intervals. |
| Portfolio implementation | engine, optimizer, BL code and saved replay | gamma 1.0, annualized prior/covariance with unconverted quarterly Q; clip then normalize; close-to-close accounting; costs on drifted-to-target trades. These are described as implemented, not silently corrected. |
| Allocation comparison | saved strategy filters | BL-Filing medium confidence versus BL-Filing MVO all confidence: configuration comparison, not isolated allocator ablation. Random baseline uses MVO and one stochastic draw. |
| Existing sensitivity | 36-case manifest, summary and validation | 2 groups × 3 Q/Ω scales × 2 gamma values × 3 allocation modes. Report separately from the primary results. Scaling is a scenario, not validated calibration. |

The source comparison is in paper/informatica/review/source_comparison.json;
the field audit is data/v2/analysis/informatica_revision/input_vintage_audit.json.
Financial results and the original protocol snapshot remain separately versioned.
Unresolved validity threats are explicitly retained in the article: temporal
model knowledge, selected surviving universe, estimate vintages and historical
strategy selection. No missing evidence has been converted into a positive claim.

## Existing sensitivity interpretation

The saved sensitivity CSV uses the same arithmetic Sharpe convention as the
main revision. Direct recomputation reproduces all 36 summary rows and both
baseline return series. The older POINT2_V1_RESULT.md narrative contains different
numbers and is not the numerical authority. The new sensitivity_audit package
records the direct CSV checks and recalculates aggregate projection effects.
No weights or trades are rerun. Provenance and all 36 configurations are retained,
including gamma 0.5; the gamma 1.0 table is a compact presentation, not a new choice
of the best configuration. Target-bound validation is scoped to individual
weights, not sector limits or production execution.

## Document versus experiment corrections

Resolved by documentation: selection date, original semantics, actual gamma,
costs, timing, filtering, provisional anonymity, shared-paper relationship.
Resolved by calculation on saved outputs: reporting window, arithmetic Sharpe,
paired uncertainty, sensitivity metrics under one risk-free convention.
Still requiring new data/design for a stronger claim: point-in-time estimates,
historical universe with exits, temporally valid model evaluation and matched
content ablations. Those experiments are not prerequisites to honestly report
the existing retrospective study, but are prerequisites to claim the corresponding
predictive or causal conclusions.
