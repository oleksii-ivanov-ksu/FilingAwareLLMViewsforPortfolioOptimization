#!/usr/bin/env python3
"""
Robustness tests addressing reviewer concerns:
1. Bootstrap CI + pairwise significance tests for ALL strategies
2. Multiple random Core/Holdout splits (10 splits)
3. Calibration (2006-2015) / Validation (2016-2025) split
4. IC analysis + Sharpe excluding 2009
5. Regime analysis for holdout

Output: data/results/robustness/
"""

import os, sys, json, logging
from pathlib import Path
from collections import defaultdict

import numpy as np
import pandas as pd
import yaml

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.backtesting.engine import generate_rebalance_dates, load_views_summary, run_backtest
from src.backtesting.metrics import (
    compute_all_metrics, sharpe_ratio, bootstrap_sharpe_ci, test_sharpe_difference,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

STRATEGIES = ["bl_llm_tilt", "bl_llm_tilt_pos", "bl_llm", "equal_weight", "mvo", "random_views"]
LABELS = {
    "bl_llm_tilt_pos": "BL-Filing+", "bl_llm_tilt": "BL-Filing", "bl_llm": "BL-Filing MVO",
    "equal_weight": "EW", "mvo": "MVO", "random_views": "Random",
}


def load_universe(path):
    with open(path) as f:
        u = yaml.safe_load(f)["universe"]
    return u.get("core", []), u.get("holdout", [])


def load_all_prices(raw_dir, tickers):
    frames = {}
    for t in tickers:
        pf = raw_dir / t / "prices.csv"
        if pf.exists():
            df = pd.read_csv(pf, parse_dates=["date"]).set_index("date").sort_index()
            frames[t] = df["close"]
    return pd.DataFrame(frames).sort_index().ffill(limit=5)


def run_strategies(prices, views_df, tickers, rebalance_dates, strategies=STRATEGIES):
    results = {}
    for strat in strategies:
        result = run_backtest(
            prices=prices, views_df=views_df, tickers=tickers,
            rebalance_dates=rebalance_dates, strategy=strat,
            tau=0.05, max_weight=0.10, transaction_cost_bps=10.0,
        )
        results[strat] = result["daily_returns"]
    return results


def main():
    base_dir = Path(".")
    raw_dir = base_dir / "data" / "raw"
    views_csv = base_dir / "data" / "views" / "views_summary.csv"
    output_dir = base_dir / "data" / "results" / "robustness"
    output_dir.mkdir(parents=True, exist_ok=True)

    core_tickers, holdout_tickers = load_universe("config/universe.yaml")
    all_tickers = core_tickers + holdout_tickers

    logger.info("Loading data...")
    views_df = load_views_summary(views_csv)
    all_prices = load_all_prices(raw_dir, all_tickers)
    all_prices = all_prices[all_prices.index <= pd.Timestamp(2026, 3, 31)]
    valid_all = [t for t in all_tickers if t in all_prices.columns]
    logger.info(f"Loaded {len(valid_all)} tickers, {all_prices.shape[0]} days")

    rebalance_dates = generate_rebalance_dates(2006, 2025, "quarterly")

    # ================================================================
    # TEST 1: Bootstrap CI + Pairwise Tests
    # ================================================================
    logger.info("=" * 60)
    logger.info("TEST 1: Bootstrap CI + Pairwise Significance")
    logger.info("=" * 60)

    # Run core backtest
    core_valid = [t for t in core_tickers if t in all_prices.columns]
    core_returns = run_strategies(all_prices, views_df, core_valid, rebalance_dates)

    # Bootstrap CI for each strategy
    ci_results = {}
    for strat in STRATEGIES:
        ci_low, ci_high = bootstrap_sharpe_ci(core_returns[strat], n_bootstrap=10000)
        sr = sharpe_ratio(core_returns[strat])
        ci_results[strat] = {"sharpe": sr, "ci_lower": ci_low, "ci_upper": ci_high}
        logger.info(f"  {LABELS[strat]:15s}: Sharpe={sr:.3f}  95% CI=[{ci_low:.3f}, {ci_high:.3f}]")

    # Pairwise tests: BL-Filing+ vs each
    pairwise_results = {}
    for baseline in STRATEGIES:
        if baseline == "bl_llm_tilt_pos":
            continue
        test = test_sharpe_difference(core_returns["bl_llm_tilt_pos"], core_returns[baseline])
        pairwise_results[f"BL-Filing+_vs_{LABELS[baseline]}"] = test
        sig = "***" if test["p_value"] < 0.01 else "**" if test["p_value"] < 0.05 else "*" if test["p_value"] < 0.10 else ""
        logger.info(f"  BL-Filing+ vs {LABELS[baseline]:15s}: diff={test['sharpe_diff']:.3f}  p={test['p_value']:.4f} {sig}")

    # Also BL-Filing vs EW
    test_bl_ew = test_sharpe_difference(core_returns["bl_llm_tilt"], core_returns["equal_weight"])
    pairwise_results["BL-Filing_vs_EW"] = test_bl_ew
    logger.info(f"  BL-Filing vs EW: diff={test_bl_ew['sharpe_diff']:.3f}  p={test_bl_ew['p_value']:.4f}")

    with open(output_dir / "bootstrap_ci.json", "w") as f:
        json.dump(ci_results, f, indent=2, default=str)
    with open(output_dir / "pairwise_tests.json", "w") as f:
        json.dump(pairwise_results, f, indent=2, default=str)

    # ================================================================
    # TEST 2: Multiple Random Splits (10 splits)
    # ================================================================
    logger.info("=" * 60)
    logger.info("TEST 2: Multiple Random Splits (10 splits)")
    logger.info("=" * 60)

    rng = np.random.default_rng(42)
    split_results = []
    test_strategies = ["bl_llm_tilt_pos", "bl_llm_tilt", "equal_weight", "mvo"]

    for split_idx in range(10):
        shuffled = rng.permutation(valid_all).tolist()
        split_core = shuffled[:50]
        split_holdout = shuffled[50:]

        for subset_name, subset_tickers in [("core", split_core), ("holdout", split_holdout)]:
            reb_dates = generate_rebalance_dates(2006, 2025, "quarterly")
            returns = run_strategies(all_prices, views_df, subset_tickers, reb_dates, test_strategies)
            for strat, rets in returns.items():
                m = compute_all_metrics(rets)
                split_results.append({
                    "split": split_idx, "subset": subset_name, "strategy": strat, **m,
                })

        # Log progress
        core_sr = [r["sharpe_ratio"] for r in split_results if r["split"]==split_idx and r["subset"]=="core" and r["strategy"]=="bl_llm_tilt_pos"]
        hold_sr = [r["sharpe_ratio"] for r in split_results if r["split"]==split_idx and r["subset"]=="holdout" and r["strategy"]=="bl_llm_tilt_pos"]
        logger.info(f"  Split {split_idx}: BL-Filing+ Core={core_sr[0]:.3f}, Holdout={hold_sr[0]:.3f}")

    split_df = pd.DataFrame(split_results)
    split_df.to_csv(output_dir / "random_splits.csv", index=False)

    # Summary
    print("\n--- RANDOM SPLITS SUMMARY (mean +/- std across 10 splits) ---")
    for strat in test_strategies:
        for subset in ["core", "holdout"]:
            mask = (split_df.strategy == strat) & (split_df.subset == subset)
            sharpes = split_df.loc[mask, "sharpe_ratio"]
            print(f"  {LABELS[strat]:15s} {subset:8s}: Sharpe = {sharpes.mean():.3f} +/- {sharpes.std():.3f}  [{sharpes.min():.3f}, {sharpes.max():.3f}]")

    # ================================================================
    # TEST 3: Calibration (2006-2015) / Validation (2016-2025)
    # ================================================================
    logger.info("=" * 60)
    logger.info("TEST 3: Calibration/Validation Split")
    logger.info("=" * 60)

    calib_results = {}
    valid_results = {}

    for period_name, start_y, end_y in [("calibration", 2006, 2015), ("validation", 2016, 2025)]:
        reb = generate_rebalance_dates(start_y, end_y, "quarterly")
        returns = run_strategies(all_prices, views_df, core_valid, reb)

        for strat, rets in returns.items():
            m = compute_all_metrics(rets)
            if period_name == "calibration":
                calib_results[strat] = m
            else:
                valid_results[strat] = m
            logger.info(f"  {period_name:12s} {LABELS[strat]:15s}: Sharpe={m['sharpe_ratio']:.3f}  Return={m['annualized_return']:.1%}")

    with open(output_dir / "calibration_validation.json", "w") as f:
        json.dump({"calibration": calib_results, "validation": valid_results}, f, indent=2, default=str)

    # ================================================================
    # TEST 4: Sharpe excluding 2009 + IC analysis
    # ================================================================
    logger.info("=" * 60)
    logger.info("TEST 4: Sharpe ex-2009 + Information Coefficient")
    logger.info("=" * 60)

    # Sharpe excluding 2009
    ex2009_results = {}
    for strat in STRATEGIES:
        rets_ex = core_returns[strat][core_returns[strat].index.year != 2009]
        m = compute_all_metrics(rets_ex)
        ex2009_results[strat] = m
        logger.info(f"  ex-2009 {LABELS[strat]:15s}: Sharpe={m['sharpe_ratio']:.3f}  (full: {sharpe_ratio(core_returns[strat]):.3f})")

    with open(output_dir / "sharpe_ex2009.json", "w") as f:
        json.dump(ex2009_results, f, indent=2, default=str)

    # IC analysis: correlation between view_bps and forward 3-month return
    logger.info("  Computing Information Coefficient...")
    prices_core = all_prices[core_valid]
    forward_3m = prices_core.pct_change(63).shift(-63)  # 63 trading days ~ 3 months

    ic_by_year = {}
    for _, row in views_df.iterrows():
        ticker = row.ticker
        view_date = pd.Timestamp(row.view_date)
        view_bps = row.view_bps

        if ticker not in forward_3m.columns:
            continue
        # Find nearest date in prices
        valid_dates = forward_3m.index[forward_3m.index >= view_date]
        if len(valid_dates) == 0:
            continue
        nearest = valid_dates[0]
        fwd_ret = forward_3m.loc[nearest, ticker]

        if pd.isna(fwd_ret) or pd.isna(view_bps):
            continue

        year = view_date.year
        if year not in ic_by_year:
            ic_by_year[year] = {"views": [], "returns": []}
        ic_by_year[year]["views"].append(view_bps)
        ic_by_year[year]["returns"].append(fwd_ret)

    ic_results = {}
    all_views_flat = []
    all_rets_flat = []
    for year in sorted(ic_by_year.keys()):
        v = ic_by_year[year]["views"]
        r = ic_by_year[year]["returns"]
        if len(v) > 5:
            from scipy.stats import spearmanr
            ic, p = spearmanr(v, r)
            ic_results[year] = {"ic": ic, "p_value": p, "n": len(v)}
            all_views_flat.extend(v)
            all_rets_flat.extend(r)
            sig = "*" if p < 0.05 else ""
            logger.info(f"  IC {year}: {ic:.3f} (n={len(v)}) {sig}")

    # Overall IC
    from scipy.stats import spearmanr
    overall_ic, overall_p = spearmanr(all_views_flat, all_rets_flat)
    ic_results["overall"] = {"ic": overall_ic, "p_value": overall_p, "n": len(all_views_flat)}
    logger.info(f"  IC overall: {overall_ic:.3f} (n={len(all_views_flat)}, p={overall_p:.4f})")

    with open(output_dir / "ic_analysis.json", "w") as f:
        json.dump(ic_results, f, indent=2, default=str)

    # ================================================================
    # TEST 5: Regime Analysis for Holdout
    # ================================================================
    logger.info("=" * 60)
    logger.info("TEST 5: Regime Analysis (Holdout)")
    logger.info("=" * 60)

    holdout_valid = [t for t in holdout_tickers if t in all_prices.columns]
    holdout_returns = run_strategies(all_prices, views_df, holdout_valid, rebalance_dates)

    regimes = {
        "GFC 2008-09": ("2008-01-01", "2009-12-31"),
        "Recovery 2010-13": ("2010-01-01", "2013-12-31"),
        "Bull 2014-19": ("2014-01-01", "2019-12-31"),
        "COVID 2020": ("2020-01-01", "2020-12-31"),
        "Post-COVID 2021-22": ("2021-01-01", "2022-12-31"),
        "AI Boom 2023-25": ("2023-01-01", "2025-12-31"),
    }

    regime_results = {"core": {}, "holdout": {}}
    for regime_name, (start, end) in regimes.items():
        regime_results["core"][regime_name] = {}
        regime_results["holdout"][regime_name] = {}

        for strat in ["bl_llm_tilt_pos", "bl_llm_tilt", "equal_weight", "mvo", "random_views"]:
            # Core
            mask_c = (core_returns[strat].index >= start) & (core_returns[strat].index <= end)
            rets_c = core_returns[strat][mask_c]
            if len(rets_c) > 20:
                regime_results["core"][regime_name][LABELS[strat]] = round(sharpe_ratio(rets_c), 3)

            # Holdout
            mask_h = (holdout_returns[strat].index >= start) & (holdout_returns[strat].index <= end)
            rets_h = holdout_returns[strat][mask_h]
            if len(rets_h) > 20:
                regime_results["holdout"][regime_name][LABELS[strat]] = round(sharpe_ratio(rets_h), 3)

        logger.info(f"  {regime_name:20s}  Core BL+={regime_results['core'][regime_name].get('BL-Filing+','N/A')}  "
                    f"Holdout BL+={regime_results['holdout'][regime_name].get('BL-Filing+','N/A')}")

    with open(output_dir / "regime_analysis.json", "w") as f:
        json.dump(regime_results, f, indent=2, default=str)

    # ================================================================
    # FINAL SUMMARY
    # ================================================================
    print("\n" + "=" * 80)
    print("ROBUSTNESS TESTS COMPLETE")
    print("=" * 80)

    print("\n1. BOOTSTRAP CI (Core, 95%):")
    for strat in STRATEGIES:
        c = ci_results[strat]
        print(f"   {LABELS[strat]:15s}: {c['sharpe']:.3f}  [{c['ci_lower']:.3f}, {c['ci_upper']:.3f}]")

    print("\n2. PAIRWISE TESTS (BL-Filing+ vs others):")
    for key, test in pairwise_results.items():
        sig = "***" if test["p_value"] < 0.01 else "**" if test["p_value"] < 0.05 else "*" if test["p_value"] < 0.10 else "n.s."
        print(f"   {key:30s}: diff={test['sharpe_diff']:+.3f}  p={test['p_value']:.4f}  {sig}")

    print("\n3. RANDOM SPLITS (BL-Filing+ Sharpe, 10 splits):")
    for subset in ["core", "holdout"]:
        mask = (split_df.strategy == "bl_llm_tilt_pos") & (split_df.subset == subset)
        sharpes = split_df.loc[mask, "sharpe_ratio"]
        print(f"   {subset:8s}: {sharpes.mean():.3f} +/- {sharpes.std():.3f}  [{sharpes.min():.3f}, {sharpes.max():.3f}]")

    print("\n4. CALIBRATION/VALIDATION:")
    for strat in ["bl_llm_tilt_pos", "bl_llm_tilt", "equal_weight", "mvo"]:
        cs = calib_results[strat]["sharpe_ratio"]
        vs = valid_results[strat]["sharpe_ratio"]
        print(f"   {LABELS[strat]:15s}: Calib={cs:.3f}  Valid={vs:.3f}  Diff={vs-cs:+.3f}")

    print("\n5. SHARPE EX-2009:")
    for strat in STRATEGIES:
        full = sharpe_ratio(core_returns[strat])
        ex = ex2009_results[strat]["sharpe_ratio"]
        print(f"   {LABELS[strat]:15s}: Full={full:.3f}  Ex-2009={ex:.3f}  Diff={ex-full:+.3f}")

    print(f"\n6. INFORMATION COEFFICIENT: overall IC={overall_ic:.3f} (p={overall_p:.4f})")

    print("\n7. REGIME ANALYSIS (Holdout Sharpe):")
    for regime_name in regimes:
        vals = regime_results["holdout"][regime_name]
        parts = [f"{k}={v}" for k, v in vals.items()]
        print(f"   {regime_name:20s}: {', '.join(parts)}")

    print(f"\nAll results saved to {output_dir}/")


if __name__ == "__main__":
    main()
