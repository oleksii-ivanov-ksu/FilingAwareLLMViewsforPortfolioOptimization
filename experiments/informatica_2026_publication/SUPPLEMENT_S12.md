## S12. Publication audit: realized RF, trading costs and statistical precision

This supplement supersedes the fixed-2% Sharpe convention in the main article. S1–S11 retain their dated calculations for auditability. Portfolio return paths, CAGR and drawdown are unchanged. All main-text Sharpe estimates use date-aligned daily RF from the cached Kenneth French file. The reported statistic is sqrt(252) times mean daily excess return divided by its sample standard deviation. It is an annualized daily statistic, not a dependence-adjusted annual-horizon ratio.

### S12.1 Metric reconciliation

The table retains both Sharpe definitions so readers can reconcile the previous manuscript and reproduction packages. The original six configurations are recomputed from saved returns truncated at 31 December 2025. Tables 2–3 use two decimal places for drawdown: Holdout EW is −56.5806695%, MVO −56.6014480%. Their earlier identical −56.6% entries were rounding, not copied paths.

| group | strategy | cagr | volatility | sharpe | fixed_2pct_sharpe | max_drawdown |
|---|---|---|---|---|---|---|
| core | bl_llm_tilt_pos | 0.1567 | 0.2457 | 0.6489 | 0.6349 | -0.5740 |
| core | bl_llm_tilt | 0.1301 | 0.2239 | 0.5857 | 0.5703 | -0.5468 |
| core | equal_weight | 0.1219 | 0.2065 | 0.5814 | 0.5647 | -0.5255 |
| core | mvo | 0.1362 | 0.2186 | 0.6192 | 0.6035 | -0.4308 |
| core | random_views | 0.0673 | 0.1546 | 0.3928 | 0.3704 | -0.3859 |
| core | bl_llm | 0.0627 | 0.1571 | 0.3617 | 0.3397 | -0.3969 |
| holdout | bl_llm_tilt_pos | 0.1324 | 0.2472 | 0.5687 | 0.5469 | -0.6365 |
| holdout | bl_llm_tilt | 0.1147 | 0.2194 | 0.5392 | 0.5146 | -0.5995 |
| holdout | equal_weight | 0.1066 | 0.2082 | 0.5217 | 0.4959 | -0.5658 |
| holdout | mvo | 0.0882 | 0.2231 | 0.4261 | 0.4020 | -0.5660 |
| holdout | random_views | 0.0778 | 0.1609 | 0.4570 | 0.4235 | -0.3915 |
| holdout | bl_llm | 0.0809 | 0.1617 | 0.4731 | 0.4397 | -0.4126 |

### S12.2 Costs and turnover

At each executed rebalance, L1 turnover is sum(abs(target − drifted weight)). Annual turnover divides its sum by T/252; one-way turnover is half the L1 value. Effective target holdings are 1/sum(w²), averaged over executed target periods. Empty holding intervals and the terminal target whose trade falls in 2026 are excluded. The same gross return and weight paths are repriced at 5, 10 and 20 bp per L1 unit. Costs are deducted from the first daily return of the corresponding holding interval, matching the saved engine convention. This calculation excludes spread, impact and changes in execution behaviour.

An independent reconstruction from asset prices and target weights reproduced the net paths within 9 × 10⁻¹⁶. The 10 bp scenario exactly reproduces the saved series. Full results for all six diagnostic arms are in results/costs.csv.

| group | strategy | cost_bps | annual_l1_turnover | mean_effective_holdings | cagr | sharpe |
|---|---|---|---|---|---|---|
| core | real | 5 | 2.2408 | 29.2288 | 0.1580 | 0.6534 |
| core | prior_only | 5 | 0.8941 | 30.9660 | 0.1549 | 0.6151 |
| core | equal_weight | 5 | 0.3726 | 50.0000 | 0.1221 | 0.5823 |
| core | volatility_tilt | 5 | 0.8686 | 28.4160 | 0.1791 | 0.6962 |
| core | real | 10 | 2.2408 | 29.2288 | 0.1567 | 0.6489 |
| core | prior_only | 10 | 0.8941 | 30.9660 | 0.1544 | 0.6134 |
| core | equal_weight | 10 | 0.3726 | 50.0000 | 0.1219 | 0.5814 |
| core | volatility_tilt | 10 | 0.8686 | 28.4160 | 0.1785 | 0.6945 |
| core | real | 20 | 2.2408 | 29.2288 | 0.1541 | 0.6398 |
| core | prior_only | 20 | 0.8941 | 30.9660 | 0.1534 | 0.6100 |
| core | equal_weight | 20 | 0.3726 | 50.0000 | 0.1215 | 0.5796 |
| core | volatility_tilt | 20 | 0.8686 | 28.4160 | 0.1775 | 0.6912 |
| holdout | real | 5 | 2.4435 | 29.8191 | 0.1338 | 0.5736 |
| holdout | prior_only | 5 | 0.8091 | 31.8052 | 0.1288 | 0.5367 |
| holdout | equal_weight | 5 | 0.3559 | 50.0000 | 0.1068 | 0.5226 |
| holdout | volatility_tilt | 5 | 0.8087 | 29.2812 | 0.1368 | 0.5670 |
| holdout | real | 10 | 2.4435 | 29.8191 | 0.1324 | 0.5687 |
| holdout | prior_only | 10 | 0.8091 | 31.8052 | 0.1284 | 0.5352 |
| holdout | equal_weight | 10 | 0.3559 | 50.0000 | 0.1066 | 0.5217 |
| holdout | volatility_tilt | 10 | 0.8087 | 29.2812 | 0.1363 | 0.5654 |
| holdout | real | 20 | 2.4435 | 29.8191 | 0.1297 | 0.5588 |
| holdout | prior_only | 20 | 0.8091 | 31.8052 | 0.1274 | 0.5321 |
| holdout | equal_weight | 20 | 0.3559 | 50.0000 | 0.1062 | 0.5200 |
| holdout | volatility_tilt | 20 | 0.8087 | 29.2812 | 0.1354 | 0.5623 |

### S12.3 DSR scenarios

The candidate set contains six original configurations and 18 saved sensitivity paths per group (the grid has 36 paths across both groups). One duplicate is removed at absolute path tolerance 1e−12, leaving 23 unique paths. Dispersion is the sample standard deviation of their daily Sharpe estimates. For assumed effective trial count N > 1, the annualized selection threshold is sqrt(252) times dispersion times [(1−γ)Φ⁻¹(1−1/N)+γΦ⁻¹(1−1/(Ne))], with Euler–Mascheroni γ. N=1 uses zero. The moment-based standard error is sqrt([1−skew·SR+(Pearson kurtosis−1)SR²/4]/[T−1]); DSR is Φ((SR−threshold_daily)/SE). These equations follow Bailey and López de Prado (2014), DOI 10.3905/jpm.2014.40.5.094.

The observed candidate set is neither the complete development history nor a random sample of independent strategies. Hence N=1,6,24,42,100 are sensitivity assumptions, and the reported values are not a global correction for all searches. In particular, 42 does not mean 42 observed candidates in either group. A high DSR concerns performance relative to a selection-adjusted zero-Sharpe benchmark; it does not test improvement over EW or isolate filing content.

A separate HAC sensitivity replaces the moment SE with a Bartlett-lag21 SE for the daily Sharpe influence function ψ_t=(e_t−μ)/σ−μ[(e_t−μ)²−σ²]/(2σ³), including the finite-sample n/(n−1) variance multiplier. This is labelled HAC probabilistic-Sharpe sensitivity, not the original DSR estimator.

| group | assumed_effective_trials | unique_candidates | annualized_threshold | dsr | hac_probability |
|---|---|---|---|---|---|
| core | 1 | 23 | 0.0000 | 0.9979 | 0.9992 |
| core | 6 | 23 | 0.0950 | 0.9928 | 0.9964 |
| core | 24 | 23 | 0.1446 | 0.9871 | 0.9928 |
| core | 42 | 23 | 0.1614 | 0.9844 | 0.9910 |
| core | 100 | 23 | 0.1849 | 0.9799 | 0.9879 |
| holdout | 1 | 23 | 0.0000 | 0.9928 | 0.9950 |
| holdout | 6 | 23 | 0.0449 | 0.9879 | 0.9911 |
| holdout | 24 | 23 | 0.0683 | 0.9843 | 0.9883 |
| holdout | 42 | 23 | 0.0762 | 0.9829 | 0.9871 |
| holdout | 100 | 23 | 0.0873 | 0.9808 | 0.9853 |

### S12.4 Conditional precision and inference

For paired Sharpe differences, the same sampled dates are used for both portfolios and daily RF is sampled with returns. Circular moving blocks have lengths 5, 21 and 63, with 10,000 draws and recorded deterministic seeds. The standard deviation of bootstrap differences estimates SE. Under a local normal approximation, MDE at two-sided α=.05 and 80% power is (Φ⁻¹(.975)+Φ⁻¹(.80))SE. The Bonferroni-six sensitivity replaces .975 with 1−.05/12. These are conditional precision estimates under the saved-series/resampling assumptions, not observed power, evidence of equivalence or a prospective sample-size guarantee. The reported main EW calculation uses the same bootstrap draws as Table 4; diagnostic-control comparisons use their separately recorded stream.

| group | a | b | difference | low | high | mde_80 | mde_80_bonferroni6 |
|---|---|---|---|---|---|---|---|
| core | bl_llm_tilt_pos | equal_weight | 0.0675 | -0.0445 | 0.1680 | 0.1528 | 0.1897 |
| core | bl_llm_tilt_pos | mvo | 0.0296 | -0.2310 | 0.2809 | 0.3674 | 0.4563 |
| core | bl_llm_tilt | bl_llm | 0.2240 | -0.0201 | 0.4653 | 0.3502 | 0.4350 |
| core | real | prior_only | 0.0355 | -0.0449 | 0.1164 | 0.1148 | 0.1425 |
| core | real | volatility_tilt | -0.0456 | -0.1221 | 0.0276 | 0.1071 | 0.1330 |
| holdout | bl_llm_tilt_pos | equal_weight | 0.0470 | -0.0483 | 0.1396 | 0.1337 | 0.1661 |
| holdout | bl_llm_tilt_pos | mvo | 0.1426 | -0.0888 | 0.3777 | 0.3350 | 0.4161 |
| holdout | bl_llm_tilt | bl_llm | 0.0661 | -0.1872 | 0.3047 | 0.3496 | 0.4343 |
| holdout | real | prior_only | 0.0335 | -0.0396 | 0.1062 | 0.1051 | 0.1306 |
| holdout | real | volatility_tilt | 0.0033 | -0.0702 | 0.0797 | 0.1065 | 0.1323 |

Full 5/21/63-day intervals, common-window metrics, grid metrics and both RF conventions are in results/. Source hashes and independent numerical checks accompany the calculations. The offline verifier checks hashes, recomputes metrics, cost scenarios, candidate-count/DSR scenarios and all reported bootstrap contrasts.

### S12.5 Experimental accounting and shared manuscript

The new model-response total is 300 pilot + 1,791 content-ablation + 1,194 masking = 3,285. The two 199-input experiments contain 2,985 responses; the pilot is additional. Publication-audit calculations make no new model calls. The companion manuscript, “Comparing LLM Pipeline Architectures for Portfolio Views from Financial Filings,” shares project data but addresses architecture, quote verification and top/bottom selection. Its results are not independent replications of the present financial evaluation. The overlap is disclosed in the article and cover letter.
