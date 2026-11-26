# Portfolio identity sensitivity — protocol v1, 2026-11-16

Scope: four fixed 50-stock slices (Core/Holdout × 2015-09-30/2025-09-30).
Dates are September quarter-ends ten years apart, chosen without optimizing
portfolio returns. Latest saved view on/before date, maximum age 120 days.
There are 199 reconstructed inputs. MO has no fresh view in the 2025 Holdout
slice and remains investable without a view in both conditions. No substitution.
This is a small descriptive mechanism diagnostic, not independent market periods.

Intervention: remove explicit company legal/short names and ticker occurrences
using recorded exact spans. Preserve all remaining text, numbers, dates, sector,
products, events and counterparties. This deliberately narrow intervention is
not complete anonymity and differs from the earlier broad 50-document pilot.
It tests explicit identity cues while minimizing loss of other economic context.
All reconstructed saved-input summaries must match before calls; exact original
historical requests were not retained. Extraction remains historical v1.

Model: x-ai/grok-4.3 via OpenRouter, provider only xai, no fallback, temperature
0.3, max_tokens 2000, JSON object, no tools/search. Three original and three
masked calls per input, 1194 jobs in frozen randomized order. New batch requires
explicit authorization. Proposed ceiling USD 10, expected about USD 2.65 using
previous measured average (not a quote or guarantee). Prices checked 2026-11-16:
USD 1.25/M input and 2.50/M output, without cache discount. Stop before any call
whose conservative maximum charge would exceed remaining authorized budget.
No automatic retry after ambiguous transport failure; preserve attempts/IDs.
Missing/invalid outputs must be reported; do not replace documents or select
favourable repeats. Current model is not historical Grok 4.1 Fast replication.

Primary allocation: for each of three repetitions, construct a full cross-section
using that repetition's views, retaining new medium-confidence positive outputs.
Use unchanged historical covariance/prior and sentiment adjustment, confidence
mapping, gamma 1, clip/normalize and no-view fallback. Each original and masked
portfolio is a feasible output from one repeated cross-section. Do not average
views before applying a nonlinear filter/allocation and call it a typical draw.

Report all four slices: 0.5*L1 between mean weight vectors; mean pairwise L1
within each condition and cross-condition; cross minus average within; changes
in HHI, maximum weight and selected-view membership; confidence transitions.
Report costs only as hypothetical 10-bps*L1 reallocation charges, not realized
turnover or strategy performance. No returns generated from two selected dates.
No stock-level bootstrap treating correlated portfolio weights as independent.
No significance claim across four dependent slices.

Secondary frozen-support diagnostic: keep historical accepted ticker set and
historical Omega, vary only new Q. Negative new Q is allowed in this diagnostic
because the support is fixed, explicitly distinct from BL-Filing+. Separates
numerical sensitivity from filter-membership changes. No assertion that it is a
new investable strategy. Save all targets and per-document outputs and hashes.
