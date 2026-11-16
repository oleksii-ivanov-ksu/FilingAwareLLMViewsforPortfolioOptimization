# Reanalysis of saved portfolio returns

Specified 2026-11-16 before running the new block-bootstrap calculation. This is
a post hoc reanalysis informed by the original results, not preregistration.
No new model calls, asset selection, weights or backtest simulation are involved.

Primary reporting windows: each saved series from its first observation through
2025-12-31. Common-window comparison: 2007-04-27 through 2025-12-31, identical
dates for Core and Holdout. Exclude 13 saved 2026 observations in each split;
do not invent a terminal liquidation or its transaction cost.

Sharpe = sqrt(252) mean(r − rf_daily)/sd(r), sample sd, rf_daily = 1.02^(1/252)−1.
CAGR and annualized volatility are separate. Report maximum drawdown and total
return. Preserve the legacy (CAGR−0.02)/volatility only in the audit supplement.
Constant 2% is a transparent reporting assumption, not an observed historical
risk-free series. No new Sortino claims are needed.

Three planned contrasts per split: BL-Filing+ minus EW; BL-Filing+ minus MVO;
BL-Filing (all medium-confidence signs) minus BL-Filing MVO. The last contrast
addresses the saved allocation-rule comparison without changing the sign filter.
Random Views remains descriptive because the saved baseline differs in allocation
and is only one stochastic realization; it cannot identify information value.

Paired circular moving-block bootstrap, 10,000 draws, common date indices across
all six strategies. Main block length 21 trading days; sensitivity 5 and 63.
Report percentile 95% intervals for Sharpe contrasts, not p-values from a mean
return test. Intervals are pointwise, non-studentized, conditional on the saved
strategies and dependence approximation; they do not correct strategy selection
or establish stationarity across a twenty-year sample.

Separately test mean daily-return contrasts using an intercept-only HAC/Bartlett
variance, lag 21 (sensitivity 5,63), n/(n−1) finite-sample correction and normal
asymptotics. Holm corrects six tests (three contrasts × two splits), separately
within each window/lag. It does not correct the historical search over settings.
Annualized mean differences = 252 × daily difference, not differences of CAGRs.
Seeds and input hashes are retained. Inspect all contrasts, including null results.

Regime summaries and common-window degradation are descriptive. Restrict existing
legacy random-split/tuning tables to a clearly labelled audit supplement if their
underlying daily series are unavailable; never relabel legacy ratios as Sharpe.
Temporal model contamination, historical estimate vintages and survivorship remain
limitations of the underlying experiment.
