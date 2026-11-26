# Filing-summary content ablation — protocol v1, 2026-11-16

User authorized the proposed three-condition pilot up to USD 10. This is a new
batch, separate from the completed 300- and 1,194-response experiments. No
full-corpus inference, journal submission or external publication is included.

Question: how much do saved filing-derived summaries change second-stage views
and portfolio weights relative to financial context alone or mismatched text?
This is a conditional sensitivity diagnostic, not a test of profitable forecasts.

Use the same 199 cases and two dates (2015-09-30, 2025-09-30), Core and Holdout.
All 50 stocks remain in each portfolio; 2025 Holdout MO has no eligible input
and remains without a view. No outcome-based sample or date reselection.

Three conditions, each with three fresh requests per case:
1. real_text: recipient financial context plus its original filing summaries;
2. no_text: exactly the same context, with both filing-summary sections removed;
3. shuffled_text: exactly the same context plus another case's summary block.

The intervention covers complete Latest 10-K/10-Q Summary blocks, including
sentiment, guidance and numbers embedded in their narrative. The separate Most
Recent Earnings and Recent Performance blocks are byte-identical, as are the
recipient identity/sector header and system prompt. 'Without text' means without
these filing summaries, not without company metadata or language in the prompt.
This tests the saved structured summaries rather than the full raw filings.

Use one fixed derangement within each date/group, seed 20261117; no self-donors.
Each donor appears once in its slice. Repeated shuffled requests use the same
donor so their variability is request variability, not changing permutations.
The single permutation is a limited placebo, not a permutation ensemble.
Donor sector, filing dates and narrative identity clues may differ. Thus the
shuffle tests mismatched disclosure bundles and may induce conflicting context;
it does not isolate a pure semantic-information effect. Preserve the donor block
verbatim and record provenance rather than silently rewriting its company facts.
Use the portfolio quarter-end as the common prompt decision date in all arms;
all supplied filing dates must precede it. Numerical context remains the saved
context, with no certification of historical vintages or model availability.

Model x-ai/grok-4.3, OpenRouter, xai only, fallback off, temperature 0.3,
max_tokens 2000, JSON, no tools or search. 1,791 calls in frozen randomized order,
eight workers, no automatic retries. Prices checked from the OpenRouter model
catalog: USD 1.25/M input and 2.50/M output, ignoring cache discounts. Budget
ceiling USD 10, conservative per-request reservations plus completed charges.
Fresh real_text calls are required because the decision-date header differs
from the prior experiment. No old responses are pooled with this batch.

Report all valid/invalid calls, unique generation IDs, actual cost and any
missingness. Stop on ambiguous transport/billing failure; do not silently replace
cases or select repetitions. Freeze input hashes and runner before execution.

Prespecified analysis: all three pairwise contrasts (real/no, real/shuffled,
shuffled/no). View-level signed and absolute differences of three-response
means, sign-category changes, confidence frequencies, cross/within absolute
distances and their difference. Report all four slices as well as descriptive
pooled case summaries; cases share companies/dates and are not independent
market experiments. No exploratory p-value hunting or population-effect claim.

Primary weights: positive medium-confidence filter, same covariance and EW prior,
historical BL/tilt formula, gamma 1 and clip-normalize. Fix sentiment to neutral
in ALL arms, using sigma 0.03 for accepted views: otherwise no_text would still
receive filing sentiment through Omega. Do not call these new portfolios exact
replications of the historical sentiment-adjusted strategy. No accepted views
means EW, consistently across conditions. No new returns are generated.

Secondary fixed support: all available input cases, sigma 0.03 in all arms,
including negative/zero views regardless of confidence. This isolates the view
magnitude interface conditional on this support; it is not BL-Filing+.

For each repetition, construct full weights before averaging. Report half-L1
distance between mean weight vectors, all three within-condition pair distances,
nine cross-condition pair distances, cross minus average within, accepted counts,
HHI and maximum weight. Four dependent slices do not justify population intervals.
No historical sentiment enters either allocation. Check same outputs yield same
weights and compare neutral-sentiment allocation with the established helper.

Decision use: a separation above repeat variability can motivate a larger
content ablation; sensitivity alone is not usefulness or return improvement.
Weak/no separation discourages scaling this exact diagnostic, without proving
that filing text is useless. A temporally valid profitability test remains separate.
