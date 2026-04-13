#!/usr/bin/env python3
"""
Generate backtest result figures for the paper.

Reads from data/results/{core,holdout}/daily_returns.csv
Produces figures in figures/

Usage:
    python scripts/plot_backtest_results.py
"""

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from pathlib import Path
import json

plt.rcParams.update({
    'figure.dpi': 150, 'savefig.dpi': 300, 'savefig.bbox': 'tight',
    'font.size': 11, 'axes.titlesize': 13, 'axes.labelsize': 11,
    'figure.facecolor': 'white', 'axes.facecolor': 'white',
    'axes.grid': True, 'grid.alpha': 0.3,
})

FIGURES_DIR = Path('figures')
FIGURES_DIR.mkdir(exist_ok=True)

# Strategy display config
STRATEGY_CONFIG = {
    'bl_llm_tilt':     {'label': 'BL-Filing',            'color': '#17becf', 'lw': 2.0, 'ls': '-'},
    'bl_llm_tilt_pos': {'label': 'BL-Filing+',           'color': '#2ca02c', 'lw': 2.5, 'ls': '-'},
    'bl_llm':          {'label': 'BL-Filing MVO',        'color': '#9467bd', 'lw': 1.2, 'ls': ':'},
    'equal_weight':    {'label': 'Equal Weight (1/N)',    'color': '#1f77b4', 'lw': 1.5, 'ls': '-'},
    'mvo':             {'label': 'MVO (Markowitz)',       'color': '#ff7f0e', 'lw': 1.2, 'ls': '-.'},
    'random_views':    {'label': 'Random Views',          'color': '#7f7f7f', 'lw': 1.0, 'ls': '--'},
}

CRISIS_PERIODS = [
    ('2007-10-01', '2009-03-31', 'GFC', '#d62728'),
    ('2020-02-15', '2020-06-30', 'COVID', '#ff7f0e'),
]


def load_returns(subset: str) -> pd.DataFrame:
    path = Path(f'data/results/{subset}/daily_returns.csv')
    df = pd.read_csv(path, index_col=0, parse_dates=True)
    return df


def load_metrics(subset: str) -> dict:
    path = Path(f'data/results/{subset}/metrics.json')
    with open(path) as f:
        return json.load(f)


def plot_cumulative_returns(core_ret, holdout_ret):
    """Figure 2: Cumulative returns — main paper figure."""
    fig, axes = plt.subplots(1, 2, figsize=(16, 6), sharey=True)

    main_strategies = ['bl_llm_tilt_pos', 'bl_llm_tilt', 'bl_llm', 'equal_weight', 'mvo', 'random_views']

    for ax, (returns, title) in zip(axes, [(core_ret, 'Core Portfolio (50 stocks)'),
                                            (holdout_ret, 'Holdout Portfolio (50 stocks)')]):
        for strat in main_strategies:
            if strat not in returns.columns:
                continue
            cfg = STRATEGY_CONFIG[strat]
            cum = (1 + returns[strat]).cumprod()
            ax.plot(cum.index, cum.values, label=cfg['label'],
                    color=cfg['color'], linewidth=cfg['lw'], linestyle=cfg['ls'])

        # Crisis shading
        for start, end, label, color in CRISIS_PERIODS:
            ax.axvspan(pd.Timestamp(start), pd.Timestamp(end), alpha=0.08, color=color)
            mid = pd.Timestamp(start) + (pd.Timestamp(end) - pd.Timestamp(start)) / 2
            ax.text(mid, ax.get_ylim()[0] * 1.05 if ax.get_ylim()[0] > 0 else 0.5,
                    label, ha='center', fontsize=8, color=color, fontweight='bold')

        ax.set_title(title, fontweight='bold')
        ax.set_ylabel('Growth of $1')
        ax.set_xlabel('')
        ax.legend(loc='upper left', fontsize=8)
        ax.set_yscale('log')
        ax.yaxis.set_major_formatter(plt.FuncFormatter(lambda x, _: f'${x:.0f}'))

    fig.suptitle('Cumulative Returns: All Strategies (2006-2025)', fontsize=15, fontweight='bold')
    plt.tight_layout()
    fig.savefig(FIGURES_DIR / 'fig2_cumulative_returns.png')
    plt.close()
    print('Saved: fig2_cumulative_returns.png')


def plot_drawdown(core_ret):
    """Figure 3: Drawdown chart."""
    fig, ax = plt.subplots(figsize=(14, 5))

    strategies = ['bl_llm_tilt_pos', 'bl_llm_tilt', 'bl_llm', 'equal_weight', 'mvo', 'random_views']

    for strat in strategies:
        if strat not in core_ret.columns:
            continue
        cfg = STRATEGY_CONFIG[strat]
        cum = (1 + core_ret[strat]).cumprod()
        peak = cum.cummax()
        dd = (cum - peak) / peak * 100

        ax.fill_between(dd.index, dd.values, 0, alpha=0.10, color=cfg['color'])
        ax.plot(dd.index, dd.values, label=f"{cfg['label']} (max: {dd.min():.1f}%)",
                color=cfg['color'], linewidth=cfg['lw'])

    for start, end, label, color in CRISIS_PERIODS:
        ax.axvspan(pd.Timestamp(start), pd.Timestamp(end), alpha=0.06, color=color)

    ax.set_ylabel('Drawdown (%)')
    ax.set_title('Drawdown Comparison — Core Portfolio', fontsize=13, fontweight='bold')
    ax.legend(loc='lower left', fontsize=9)
    ax.set_ylim(bottom=-70)

    plt.tight_layout()
    fig.savefig(FIGURES_DIR / 'fig3_drawdown.png')
    plt.close()
    print('Saved: fig3_drawdown.png')


def plot_rolling_sharpe(core_ret):
    """Figure 4: Rolling 1-year Sharpe ratio."""
    fig, ax = plt.subplots(figsize=(14, 5))

    window = 252
    strategies = ['bl_llm_tilt_pos', 'bl_llm_tilt', 'bl_llm', 'equal_weight', 'mvo', 'random_views']
    rf_daily = (1.02) ** (1/252) - 1

    for strat in strategies:
        if strat not in core_ret.columns:
            continue
        cfg = STRATEGY_CONFIG[strat]
        excess = core_ret[strat] - rf_daily
        rolling_mean = excess.rolling(window).mean() * 252
        rolling_std = core_ret[strat].rolling(window).std() * np.sqrt(252)
        rolling_sr = rolling_mean / rolling_std

        ax.plot(rolling_sr.index, rolling_sr.values,
                label=cfg['label'], color=cfg['color'], linewidth=cfg['lw'], alpha=0.8)

    ax.axhline(0, color='gray', linewidth=0.5)

    for start, end, label, color in CRISIS_PERIODS:
        ax.axvspan(pd.Timestamp(start), pd.Timestamp(end), alpha=0.06, color=color)

    ax.set_ylabel('Rolling Sharpe Ratio (1Y)')
    ax.set_title('Rolling Sharpe Ratio — Core Portfolio', fontsize=13, fontweight='bold')
    ax.legend(loc='upper right', fontsize=9)
    ax.set_ylim(-3, 5)

    plt.tight_layout()
    fig.savefig(FIGURES_DIR / 'fig4_rolling_sharpe.png')
    plt.close()
    print('Saved: fig4_rolling_sharpe.png')


def plot_strategy_comparison_table(core_metrics, holdout_metrics):
    """Figure: Summary comparison table as image."""
    fig, ax = plt.subplots(figsize=(14, 5))
    ax.axis('off')

    strategies = ['bl_llm_tilt_pos', 'bl_llm_tilt', 'bl_llm', 'equal_weight', 'mvo', 'random_views']
    columns = ['Strategy', 'Ann.Ret', 'Ann.Vol', 'Sharpe', 'Sortino', 'MaxDD', 'Total Ret']

    # Core data
    rows = []
    for s in strategies:
        if s not in core_metrics:
            continue
        m = core_metrics[s]
        cfg = STRATEGY_CONFIG.get(s, {'label': s})
        rows.append([
            cfg['label'],
            f"{m['annualized_return']:.1%}",
            f"{m['annualized_volatility']:.1%}",
            f"{m['sharpe_ratio']:.3f}",
            f"{m['sortino_ratio']:.3f}",
            f"{m['max_drawdown']:.1%}",
            f"{m['total_return']:.1%}",
        ])

    table = ax.table(cellText=rows, colLabels=columns, loc='center', cellLoc='center')
    table.auto_set_font_size(False)
    table.set_fontsize(10)
    table.scale(1, 1.5)

    # Color header
    for j in range(len(columns)):
        table[0, j].set_facecolor('#4C72B0')
        table[0, j].set_text_props(color='white', fontweight='bold')

    # Highlight our strategies (rows 1, 2, 3 = BL-Filing+, BL-Filing, BL-Filing MVO)
    for j in range(len(columns)):
        table[1, j].set_facecolor('#d5e8d4')
        table[2, j].set_facecolor('#e8f5e8')
        table[3, j].set_facecolor('#f0f0f0')

    ax.set_title('Core Portfolio Results (2006-2025, Quarterly Rebalancing)', fontsize=14, fontweight='bold', pad=20)

    plt.tight_layout()
    fig.savefig(FIGURES_DIR / 'fig_results_table_core.png')
    plt.close()
    print('Saved: fig_results_table_core.png')


def plot_core_vs_holdout(core_metrics, holdout_metrics):
    """Figure 13: Core vs Holdout comparison."""
    fig, axes = plt.subplots(1, 3, figsize=(18, 6))

    strategies = ['bl_llm_tilt_pos', 'bl_llm_tilt', 'bl_llm', 'equal_weight', 'mvo', 'random_views']
    labels = [STRATEGY_CONFIG[s]['label'] for s in strategies]
    colors = [STRATEGY_CONFIG[s]['color'] for s in strategies]

    metrics_list = [
        ('sharpe_ratio', 'Sharpe Ratio', axes[0]),
        ('annualized_return', 'Annualized Return', axes[1]),
        ('max_drawdown', 'Max Drawdown', axes[2]),
    ]

    x = np.arange(len(strategies))
    w = 0.30

    for metric_key, metric_name, ax in metrics_list:
        core_vals = [core_metrics.get(s, {}).get(metric_key, 0) for s in strategies]
        hold_vals = [holdout_metrics.get(s, {}).get(metric_key, 0) for s in strategies]

        bars1 = ax.bar(x - w/2, core_vals, w, label='Core', color=colors, alpha=0.8, edgecolor='white')
        bars2 = ax.bar(x + w/2, hold_vals, w, label='Holdout', color=colors, alpha=0.4, edgecolor='white', hatch='//')

        ax.set_xticks(x)
        ax.set_xticklabels([l.split('(')[0].strip() for l in labels], fontsize=8, rotation=15)
        ax.set_title(metric_name, fontweight='bold')

        if metric_key == 'annualized_return':
            ax.yaxis.set_major_formatter(plt.FuncFormatter(lambda v, _: f'{v:.0%}'))
        elif metric_key == 'max_drawdown':
            ax.yaxis.set_major_formatter(plt.FuncFormatter(lambda v, _: f'{v:.0%}'))

    axes[0].legend(['Core', 'Holdout'], fontsize=9)
    fig.suptitle('Core vs Holdout: Out-of-Sample Validation', fontsize=14, fontweight='bold')
    plt.tight_layout()
    fig.savefig(FIGURES_DIR / 'fig13_core_vs_holdout.png')
    plt.close()
    print('Saved: fig13_core_vs_holdout.png')


def plot_annual_returns(core_ret):
    """Annual returns comparison bar chart — all main strategies."""
    fig, ax = plt.subplots(figsize=(16, 7))

    strategies = ['bl_llm_tilt_pos', 'bl_llm_tilt', 'bl_llm', 'equal_weight', 'mvo', 'random_views']
    years = sorted(core_ret.index.year.unique())

    x = np.arange(len(years))
    n = len(strategies)
    w = 0.8 / n  # bar width

    for i, strat in enumerate(strategies):
        if strat not in core_ret.columns:
            continue
        cfg = STRATEGY_CONFIG[strat]
        annual = core_ret[strat].groupby(core_ret.index.year).apply(lambda r: (1 + r).prod() - 1)
        offset = (i - n/2 + 0.5) * w
        ax.bar(x + offset, annual.values * 100, w,
               label=cfg['label'], color=cfg['color'], alpha=0.8, edgecolor='white')

    ax.set_xticks(x)
    ax.set_xticklabels(years, rotation=45, fontsize=9)
    ax.set_ylabel('Annual Return (%)')
    ax.set_title('Annual Returns by Strategy — Core Portfolio', fontsize=13, fontweight='bold')
    ax.legend(fontsize=9, loc='upper left')
    ax.axhline(0, color='gray', linewidth=0.5)

    # Shade crisis years
    for year_idx, year in enumerate(years):
        if year in (2008, 2009, 2020):
            ax.axvspan(year_idx - 0.5, year_idx + 0.5, alpha=0.05, color='red')

    plt.tight_layout()
    fig.savefig(FIGURES_DIR / 'fig_annual_returns.png')
    plt.close()
    print('Saved: fig_annual_returns.png')


def compute_regime_sharpe(returns, rf_annual=0.02):
    """Compute Sharpe ratio for a return series."""
    ann_ret = (1 + returns).prod() ** (252 / len(returns)) - 1
    ann_vol = returns.std() * np.sqrt(252)
    if ann_vol == 0:
        return 0.0
    return (ann_ret - rf_annual) / ann_vol


def plot_regime_performance(core_ret):
    """Figure 8: Sharpe by market regime — bar chart."""
    regimes = {
        'GFC\n2008-09': ('2008-01-01', '2009-12-31'),
        'Recovery\n2010-13': ('2010-01-01', '2013-12-31'),
        'Bull\n2014-19': ('2014-01-01', '2019-12-31'),
        'COVID\n2020': ('2020-01-01', '2020-12-31'),
        'Post-COVID\n2021-22': ('2021-01-01', '2022-12-31'),
        'AI Boom\n2023-25': ('2023-01-01', '2025-12-31'),
    }

    strategies = ['bl_llm_tilt_pos', 'bl_llm_tilt', 'bl_llm', 'equal_weight', 'mvo', 'random_views']

    fig, ax = plt.subplots(figsize=(16, 7))
    x = np.arange(len(regimes))
    n = len(strategies)
    w = 0.8 / n

    for i, strat in enumerate(strategies):
        if strat not in core_ret.columns:
            continue
        cfg = STRATEGY_CONFIG[strat]
        sharpes = []
        for rname, (start, end) in regimes.items():
            mask = (core_ret.index >= start) & (core_ret.index <= end)
            rets = core_ret[strat][mask]
            sr = compute_regime_sharpe(rets) if len(rets) > 20 else 0
            sharpes.append(sr)
        offset = (i - n / 2 + 0.5) * w
        ax.bar(x + offset, sharpes, w, label=cfg['label'], color=cfg['color'], alpha=0.8, edgecolor='white')

    ax.set_xticks(x)
    ax.set_xticklabels(list(regimes.keys()), fontsize=9)
    ax.set_ylabel('Sharpe Ratio')
    ax.set_title('Sharpe Ratio by Market Regime — Core Portfolio (Quarterly)', fontsize=13, fontweight='bold')
    ax.legend(fontsize=8, loc='upper left', ncol=2)
    ax.axhline(0, color='gray', linewidth=0.5)

    plt.tight_layout()
    fig.savefig(FIGURES_DIR / 'fig8_regime_performance.png')
    plt.close()
    print('Saved: fig8_regime_performance.png')


def main():
    print('Loading results...')
    core_ret = load_returns('core')
    holdout_ret = load_returns('holdout')
    core_metrics = load_metrics('core')
    holdout_metrics = load_metrics('holdout')

    print(f'Core: {core_ret.shape[0]} days, {core_ret.shape[1]} strategies')
    print(f'Holdout: {holdout_ret.shape[0]} days, {holdout_ret.shape[1]} strategies')
    print()

    print('Generating figures...')
    plot_cumulative_returns(core_ret, holdout_ret)
    plot_drawdown(core_ret)
    plot_rolling_sharpe(core_ret)
    plot_strategy_comparison_table(core_metrics, holdout_metrics)
    plot_core_vs_holdout(core_metrics, holdout_metrics)
    plot_annual_returns(core_ret)
    plot_regime_performance(core_ret)

    print()
    print('All backtest figures saved to figures/')


if __name__ == '__main__':
    main()
