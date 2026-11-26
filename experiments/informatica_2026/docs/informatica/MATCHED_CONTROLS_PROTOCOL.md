# Matched saved-view controls — protocol v1, 2026-11-16

Fixed before inspecting outputs of these new controls; post hoc relative to the
known historical experiment. Not a preregistered investment strategy.

Primary scope: historical BL-Filing+ (medium confidence, positive view), Core
and Holdout, quarterly 2006–2025, same saved v1 inputs and trading engine rules.
No new data retrieval or LLM calls. Shared/frozen files remain read-only.

Arms, fixed in advance:
1. real: reproduce historical BL-Filing+ targets and daily returns.
2. prior_only: remove P/Q/Omega, tilt the same covariance-derived prior; retain
   the real arm's no-eligible-view equal-weight fallback. This conditional prior
   control retains availability of the original signal set, not its magnitudes.
3. equal_weight: quarterly equal weighting, same costs and drift.
4. full_shuffle, 100 seeds 0..99: reassign accepted (Q, Omega) pairs without
   replacement to the full 50-stock universe on each date. This destroys joint
   company selection/value assignment, preserving count and joint distribution.
5. eligible_shuffle, 100 seeds 0..99: reassign those same pairs only among
   originally accepted tickers. This preserves selected companies, but breaks
   their value/uncertainty pairing. Confidence remains medium in every accepted
   pair; sentiment-derived uncertainty travels with Q.

Permutation key: SHA-256 of protocol seed=20261116, group, date, arm, seed.
No permutations across dates or Core/Holdout. A control's temporal signal
persistence can differ; permutation ranks are conditional diagnostics, not
causal or predictive p-values and not proof of exchangeability.

Historical semantics retained explicitly: Q / 10,000 without horizon conversion;
annualized covariance 252-day Ledoit–Wolf; prior 2.5*Sigma*equal weights; tau .05;
gamma 1.0; clip .005/.10 then renormalize (not final hard bounds); cost .001*L1
from drifted weights; following-day close-to-close return. All BL/tilting arms share known insufficient-covariance-history fallbacks;
EW does not use covariance and rebalances normally. Unexpected exceptions abort. No terminal sale.
Simulation uses the saved price horizon; output reporting ends 2025-12-31.

Outputs: all daily series, all target arrays, active-view/date manifest, source
hashes, per-seed Sharpe/CAGR/drawdown/turnover/concentration and validation.
Primary descriptive comparison: real Sharpe relative to full-shuffle distribution,
separately for each group. Report median, 2.5/97.5 percentiles, rank exceedance
(1 + count(shuffle >= real))/101; do not call these sampling confidence intervals.
Secondary: eligible shuffle, prior-only and EW. Save every seed; no selection.
Paired moving-block bootstrap (10,000 draws, 21 trading days primary; 5/63
sensitivity) compares real with prior-only, EW and ensemble-mean daily returns
of each shuffle family. The latter is not mean seed Sharpe or a tradeable fixed
strategy; intervals condition on saved realizations, without nested seed resampling.

Validation before interpretation: vectorized multi-arm simulation agrees with
shared engine and frozen real/EW series to 1e-10; permutation pairs and eligible
sets preserved; finite long-only normalized targets; no unplanned fallback.

Masking-to-weights follow-up: choose portfolio dates before new model outputs,
using coverage and calendar strata only. Use full original/latest eligible inputs,
not the existing 50 documents as a synthetic cross-sectional portfolio. Prepare
manifest and budget before any new API calls; earlier 300-call authorization is
not treated as an unlimited authorization for new experiments.

Implementation validation amendment: the first run reproduced real returns but
failed the frozen Holdout EW check because covariance fallbacks were incorrectly
applied to EW. Fixed before interpreting control results; incomplete output is
retained as matched_controls_v1_failed_ew_validation. No parameter selection.
