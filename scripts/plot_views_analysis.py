#!/usr/bin/env python3
"""
Generate descriptive statistics figures for LLM views (Phase 3 output).

Produces:
  figures/fig15_views_distribution_overview.png  — 2x2 panel (main paper)
  figures/fig_views_by_month.png                 — Filing distribution by month
  figures/fig_views_yearly_timeseries.png         — Mean view_bps by year
  figures/fig_confidence_calibration_box.png      — Box plots by confidence
  figures/fig_sentiment_vs_views.png              — Sentiment → view alignment
  figures/fig_filing_type_comparison.png          — 10-K vs 10-Q comparison
  figures/fig_eps_surprise_distribution.png       — EPS surprise histogram

Usage:
    python scripts/plot_views_analysis.py
"""

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
import seaborn as sns
from pathlib import Path

# Style
plt.rcParams.update({
    'figure.dpi': 150,
    'savefig.dpi': 300,
    'savefig.bbox': 'tight',
    'font.size': 11,
    'axes.titlesize': 13,
    'axes.labelsize': 11,
    'xtick.labelsize': 10,
    'ytick.labelsize': 10,
    'legend.fontsize': 10,
    'figure.facecolor': 'white',
    'axes.facecolor': 'white',
    'axes.grid': True,
    'grid.alpha': 0.3,
})

FIGURES_DIR = Path('figures')
FIGURES_DIR.mkdir(exist_ok=True)


def load_views():
    """Load views summary."""
    df = pd.read_csv('data/views/views_summary.csv')
    df['view_date'] = pd.to_datetime(df['view_date'])
    df['year'] = df['view_date'].dt.year
    df['month'] = df['view_date'].dt.month
    return df


def plot_fig15_overview(df):
    """Figure 15: 2x2 View Distribution Overview (main paper figure)."""
    fig, axes = plt.subplots(2, 2, figsize=(14, 10))
    fig.suptitle('LLM Views: Distribution Overview (N=8,001)', fontsize=15, fontweight='bold')

    # --- Panel A: Histogram of view_bps ---
    ax = axes[0, 0]
    ax.hist(df['view_bps'], bins=np.arange(-275, 225, 25), color='#4C72B0',
            edgecolor='white', alpha=0.85)
    ax.axvline(df['view_bps'].mean(), color='red', linestyle='--', linewidth=1.5,
               label=f'Mean = {df["view_bps"].mean():.1f} bps')
    ax.axvline(df['view_bps'].median(), color='orange', linestyle='--', linewidth=1.5,
               label=f'Median = {df["view_bps"].median():.1f} bps')
    ax.set_xlabel('View (basis points)')
    ax.set_ylabel('Count')
    ax.set_title('A. Distribution of View Predictions')
    ax.legend(loc='upper left')
    ax.text(0.97, 0.95, f'σ = {df["view_bps"].std():.1f} bps\nskew = {df["view_bps"].skew():.2f}',
            transform=ax.transAxes, ha='right', va='top',
            fontsize=9, bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.5))

    # --- Panel B: Box plots by Confidence ---
    ax = axes[0, 1]
    conf_order = ['high', 'medium', 'low']
    conf_colors = {'high': '#2ca02c', 'medium': '#4C72B0', 'low': '#d62728'}
    box_data = [df[df['confidence'] == c]['view_bps'].values for c in conf_order]
    bp = ax.boxplot(box_data, labels=['High\n(N={})'.format(len(df[df.confidence == 'high'])),
                                       'Medium\n(N={})'.format(len(df[df.confidence == 'medium'])),
                                       'Low\n(N={})'.format(len(df[df.confidence == 'low']))],
                    patch_artist=True, widths=0.5)
    for patch, c in zip(bp['boxes'], conf_order):
        patch.set_facecolor(conf_colors[c])
        patch.set_alpha(0.7)
    ax.axhline(0, color='gray', linestyle='-', linewidth=0.5)
    ax.set_ylabel('View (basis points)')
    ax.set_title('B. Views by Confidence Level')

    # Add mean annotations
    for i, c in enumerate(conf_order):
        mean_val = df[df.confidence == c]['view_bps'].mean()
        ax.text(i + 1, df[df.confidence == c]['view_bps'].max() + 15,
                f'μ={mean_val:+.0f}', ha='center', fontsize=9, fontweight='bold')

    # --- Panel C: Mean view_bps by year ---
    ax = axes[1, 0]
    yearly = df.groupby('year').agg(
        mean_bps=('view_bps', 'mean'),
        std_bps=('view_bps', 'std'),
        count=('view_bps', 'count'),
    ).reset_index()
    yearly['se'] = yearly['std_bps'] / np.sqrt(yearly['count'])

    ax.fill_between(yearly['year'], yearly['mean_bps'] - yearly['std_bps'],
                     yearly['mean_bps'] + yearly['std_bps'], alpha=0.15, color='#4C72B0')
    ax.plot(yearly['year'], yearly['mean_bps'], 'o-', color='#4C72B0', markersize=5, linewidth=1.5)
    ax.axhline(0, color='gray', linestyle='-', linewidth=0.5)

    # Shade crisis periods
    ax.axvspan(2008, 2009, alpha=0.1, color='red', label='GFC')
    ax.axvspan(2019.8, 2020.3, alpha=0.1, color='orange', label='COVID')

    ax.set_xlabel('Year')
    ax.set_ylabel('Mean View (bps)')
    ax.set_title('C. Mean View by Year (±1 std)')
    ax.legend(loc='lower left', fontsize=9)
    ax.set_xlim(2005.5, 2025.5)

    # --- Panel D: Sentiment vs Mean view_bps ---
    ax = axes[1, 1]
    sent_order = ['confident', 'optimistic', 'neutral', 'cautious', 'concerned']
    sent_colors = ['#2ca02c', '#98df8a', '#aec7e8', '#ff9896', '#d62728']
    sent_stats = []
    for s in sent_order:
        sub = df[df.sentiment == s]
        sent_stats.append({
            'sentiment': s.capitalize(),
            'mean': sub['view_bps'].mean(),
            'std': sub['view_bps'].std(),
            'se': sub['view_bps'].std() / np.sqrt(len(sub)),
            'n': len(sub),
        })
    sent_df = pd.DataFrame(sent_stats)

    bars = ax.bar(range(len(sent_order)), sent_df['mean'], yerr=sent_df['se'] * 1.96,
                  color=sent_colors, edgecolor='white', alpha=0.85, capsize=4, width=0.6)
    ax.set_xticks(range(len(sent_order)))
    ax.set_xticklabels([f"{s['sentiment']}\n(N={s['n']})" for _, s in sent_df.iterrows()],
                        fontsize=9)
    ax.axhline(0, color='gray', linestyle='-', linewidth=0.5)
    ax.set_ylabel('Mean View (bps)')
    ax.set_title('D. Views by Filing Sentiment (±95% CI)')

    # Add value labels
    for i, bar in enumerate(bars):
        val = sent_df.iloc[i]['mean']
        ax.text(bar.get_x() + bar.get_width() / 2, val + (8 if val >= 0 else -15),
                f'{val:+.0f}', ha='center', fontsize=9, fontweight='bold')

    plt.tight_layout()
    path = FIGURES_DIR / 'fig15_views_distribution_overview.png'
    fig.savefig(path)
    plt.close()
    print(f'Saved: {path}')


def plot_views_by_month(df):
    """Views distribution by month — earning seasons visualization."""
    fig, ax = plt.subplots(figsize=(12, 5))

    monthly = df.groupby('month').size()
    colors = []
    for m in range(1, 13):
        if m in (2, 3):       # Q4/10-K season
            colors.append('#d62728')
        elif m in (4, 5):     # Q1 season
            colors.append('#2ca02c')
        elif m in (7, 8):     # Q2 season
            colors.append('#ff7f0e')
        elif m in (10, 11):   # Q3 season
            colors.append('#9467bd')
        else:
            colors.append('#cccccc')

    bars = ax.bar(range(1, 13), [monthly.get(m, 0) for m in range(1, 13)],
                  color=colors, edgecolor='white', alpha=0.85)
    ax.set_xticks(range(1, 13))
    ax.set_xticklabels(['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun',
                         'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'])
    ax.set_ylabel('Number of Views')
    ax.set_title('Filing-Triggered Views by Month (N=8,001)', fontsize=13, fontweight='bold')

    # Value labels
    for bar in bars:
        h = bar.get_height()
        if h > 50:
            ax.text(bar.get_x() + bar.get_width() / 2, h + 20, str(int(h)),
                    ha='center', fontsize=9)

    # Season labels
    season_labels = [
        (2.5, '10-K / FY\nSeason', '#d62728'),
        (4.5, 'Q1\nSeason', '#2ca02c'),
        (7.5, 'Q2\nSeason', '#ff7f0e'),
        (10.5, 'Q3\nSeason', '#9467bd'),
    ]
    for x, label, color in season_labels:
        ax.text(x, max(monthly) * 0.85, label, ha='center', fontsize=10,
                fontweight='bold', color=color,
                bbox=dict(boxstyle='round,pad=0.3', facecolor='white', edgecolor=color, alpha=0.8))

    # Annotations
    ax.text(0.98, 0.95,
            'Each earning season ≈ 25% of views\n'
            '"Dead" months (Jan, Jun, Sep, Dec) < 1%',
            transform=ax.transAxes, ha='right', va='top', fontsize=9,
            bbox=dict(boxstyle='round', facecolor='lightyellow', alpha=0.8))

    plt.tight_layout()
    path = FIGURES_DIR / 'fig_views_by_month.png'
    fig.savefig(path)
    plt.close()
    print(f'Saved: {path}')


def plot_yearly_timeseries(df):
    """Mean view_bps by year with crisis highlighting."""
    fig, ax = plt.subplots(figsize=(14, 5))

    yearly = df.groupby('year').agg(
        mean_bps=('view_bps', 'mean'),
        std_bps=('view_bps', 'std'),
        pct_positive=('view_bps', lambda x: (x > 0).mean() * 100),
    ).reset_index()

    # Bar chart colored by positive/negative
    colors = ['#2ca02c' if m >= 0 else '#d62728' for m in yearly['mean_bps']]
    bars = ax.bar(yearly['year'], yearly['mean_bps'], color=colors, alpha=0.7,
                  edgecolor='white', width=0.7)

    # Crisis shading
    ax.axvspan(2007.5, 2009.5, alpha=0.08, color='red')
    ax.axvspan(2019.7, 2020.5, alpha=0.08, color='orange')
    ax.text(2008.5, yearly['mean_bps'].max() * 0.9, 'GFC', ha='center',
            fontsize=10, color='red', fontweight='bold')
    ax.text(2020, yearly['mean_bps'].max() * 0.9, 'COVID', ha='center',
            fontsize=10, color='orange', fontweight='bold')

    ax.axhline(0, color='gray', linestyle='-', linewidth=0.8)
    ax.set_xlabel('Year')
    ax.set_ylabel('Mean View (bps)')
    ax.set_title('LLM View Predictions by Year: Crisis Awareness', fontsize=13, fontweight='bold')

    # Add % positive on top
    for bar, pct in zip(bars, yearly['pct_positive']):
        h = bar.get_height()
        y_pos = h + 2 if h >= 0 else h - 5
        ax.text(bar.get_x() + bar.get_width() / 2, y_pos,
                f'{pct:.0f}%', ha='center', fontsize=8, color='gray')

    ax.set_xlim(2005.2, 2025.8)
    ax.text(0.02, 0.02, '% = fraction of positive views', transform=ax.transAxes,
            fontsize=8, color='gray')

    plt.tight_layout()
    path = FIGURES_DIR / 'fig_views_yearly_timeseries.png'
    fig.savefig(path)
    plt.close()
    print(f'Saved: {path}')


def plot_filing_type_comparison(df):
    """10-K vs 10-Q view comparison."""
    fig, axes = plt.subplots(1, 2, figsize=(12, 5))

    # Panel A: Overlaid histograms
    ax = axes[0]
    for ft, color, label in [('10-K', '#d62728', '10-K (Annual)'),
                               ('10-Q', '#4C72B0', '10-Q (Quarterly)')]:
        sub = df[df.filing_type == ft]
        ax.hist(sub['view_bps'], bins=np.arange(-275, 225, 25), alpha=0.5,
                color=color, label=f'{label} (N={len(sub)}, μ={sub.view_bps.mean():+.1f})',
                density=True, edgecolor='white')
    ax.set_xlabel('View (basis points)')
    ax.set_ylabel('Density')
    ax.set_title('A. View Distribution by Filing Type')
    ax.legend(fontsize=9)
    ax.axvline(0, color='gray', linestyle='-', linewidth=0.5)

    # Panel B: Mean by year, split by type
    ax = axes[1]
    for ft, color, marker in [('10-K', '#d62728', 's'), ('10-Q', '#4C72B0', 'o')]:
        sub = df[df.filing_type == ft].groupby('year')['view_bps'].mean()
        ax.plot(sub.index, sub.values, f'{marker}-', color=color, markersize=4,
                label=f'{ft} mean', linewidth=1.2)
    ax.axhline(0, color='gray', linestyle='-', linewidth=0.5)
    ax.set_xlabel('Year')
    ax.set_ylabel('Mean View (bps)')
    ax.set_title('B. Annual vs Quarterly Views Over Time')
    ax.legend(fontsize=9)

    fig.suptitle('10-K vs 10-Q Filing Impact on Views', fontsize=13, fontweight='bold')
    plt.tight_layout()
    path = FIGURES_DIR / 'fig_filing_type_comparison.png'
    fig.savefig(path)
    plt.close()
    print(f'Saved: {path}')


def plot_eps_surprise_distribution(df):
    """EPS surprise distribution (after GAAP fix)."""
    fig, axes = plt.subplots(1, 2, figsize=(12, 5))

    non_null = df.dropna(subset=['eps_surprise'])
    null_count = df['eps_surprise'].isna().sum()

    # Panel A: Histogram
    ax = axes[0]
    ax.hist(non_null['eps_surprise'], bins=50, color='#4C72B0', edgecolor='white', alpha=0.85)
    ax.axvline(0, color='red', linestyle='--', linewidth=1)
    ax.set_xlabel('EPS Surprise (%)')
    ax.set_ylabel('Count')
    ax.set_title('A. EPS Surprise Distribution')
    ax.text(0.97, 0.95,
            f'N = {len(non_null)} ({len(non_null)/len(df)*100:.1f}%)\n'
            f'Nullified = {null_count} ({null_count/len(df)*100:.1f}%)\n'
            f'Range: [{non_null.eps_surprise.min():.0f}%, {non_null.eps_surprise.max():.0f}%]',
            transform=ax.transAxes, ha='right', va='top', fontsize=9,
            bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.5))

    # Panel B: Scatter eps_surprise vs view_bps
    ax = axes[1]
    sample = non_null.sample(min(2000, len(non_null)), random_state=42)
    ax.scatter(sample['eps_surprise'], sample['view_bps'], alpha=0.15, s=8, color='#4C72B0')
    # Add regression line
    z = np.polyfit(non_null['eps_surprise'], non_null['view_bps'], 1)
    x_line = np.linspace(-200, 200, 100)
    ax.plot(x_line, np.polyval(z, x_line), 'r-', linewidth=1.5, label=f'slope={z[0]:.3f}')
    corr = non_null[['eps_surprise', 'view_bps']].corr().iloc[0, 1]
    ax.set_xlabel('EPS Surprise (%)')
    ax.set_ylabel('View (bps)')
    ax.set_title('B. EPS Surprise vs View Prediction')
    ax.legend(loc='upper left', fontsize=9)
    ax.text(0.97, 0.05, f'r = {corr:.3f}', transform=ax.transAxes, ha='right', fontsize=10)

    fig.suptitle('Earnings Surprise Analysis (GAAP/Adjusted Fix Applied)',
                 fontsize=13, fontweight='bold')
    plt.tight_layout()
    path = FIGURES_DIR / 'fig_eps_surprise_distribution.png'
    fig.savefig(path)
    plt.close()
    print(f'Saved: {path}')


def plot_confidence_sentiment_heatmap(df):
    """Cross-tabulation heatmap: confidence × sentiment → mean view_bps."""
    fig, ax = plt.subplots(figsize=(8, 5))

    sent_order = ['confident', 'optimistic', 'neutral', 'cautious', 'concerned']
    conf_order = ['high', 'medium', 'low']

    pivot = df.pivot_table(values='view_bps', index='confidence', columns='sentiment',
                           aggfunc='mean')
    # Reorder
    pivot = pivot.reindex(index=conf_order, columns=sent_order)

    sns.heatmap(pivot, annot=True, fmt='.0f', cmap='RdYlGn', center=0,
                linewidths=0.5, ax=ax, cbar_kws={'label': 'Mean View (bps)'})
    ax.set_xlabel('Filing Sentiment')
    ax.set_ylabel('LLM Confidence')
    ax.set_title('Mean View (bps) by Confidence × Sentiment', fontsize=13, fontweight='bold')

    plt.tight_layout()
    path = FIGURES_DIR / 'fig_confidence_sentiment_heatmap.png'
    fig.savefig(path)
    plt.close()
    print(f'Saved: {path}')


def main():
    print('Loading views data...')
    df = load_views()
    print(f'Loaded {len(df)} views')
    print()

    print('Generating figures...')
    plot_fig15_overview(df)
    plot_views_by_month(df)
    plot_yearly_timeseries(df)
    plot_filing_type_comparison(df)
    plot_eps_surprise_distribution(df)
    plot_confidence_sentiment_heatmap(df)

    print()
    print(f'All figures saved to {FIGURES_DIR}/')
    print('Done.')


if __name__ == '__main__':
    main()
