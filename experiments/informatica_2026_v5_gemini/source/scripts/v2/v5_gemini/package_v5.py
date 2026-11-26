"""Assemble the public reproduction package for the V5 (gemini-2.5-flash) article.

Reads saved outputs only; no API calls. The package is written to
paper/informatica/v5_ua/publication_reproduction/ and is then copied into the public
repository as experiments/informatica_2026_v5_gemini/.

What goes in: daily returns and weights of all portfolios, the factor file, saved statistics,
the 7,485 experiment responses (compact records plus the unmodified requests and responses),
the experiment inputs, the gold standard with the answers of eight models, the stage-one and
stage-two outputs for the whole corpus, a source snapshot and a standalone verifier.
What stays out: price history (licensed market data), API credentials, the manuscript.
"""
from pathlib import Path
import gzip
import hashlib
import json
import logging
import re
import shutil
import sys
import zipfile
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
BASE = ROOT / 'data/v2/analysis/informatica_v5_gemini'
OUT = ROOT / 'paper/informatica/v5_ua/publication_reproduction'
HERE = Path(__file__).resolve().parent
SETS = [('original', 'llm_inputs_v1', '_gemini25flash_v1'), ('extra', 'llm_inputs_extra_dates_v1', '_gemini25flash_extra_dates_v1')]
ARMS = {'ablation': ['real_text', 'no_text', 'shuffled_text'], 'masking': ['original', 'anonymized']}
FORBIDDEN = [r'/' + r'Users/', r'sk' + r'-or-[A-Za-z0-9-]{8,}', r'sk' + r'-[A-Za-z0-9]{20,}', r'Bear' + r'er\s+[A-Za-z0-9_-]{16,}']  # literal credentials or local paths; split so this file passes its own scan


def copy(src, dst):
    dst = OUT / dst
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(src, dst)


def write_json(dst, obj):
    dst = OUT / dst
    dst.parent.mkdir(parents=True, exist_ok=True)
    dst.write_text(json.dumps(obj, ensure_ascii=False, indent=1) + '\n')


def public_bytes(p):
    """Run metadata is published without the internal note on who approved the spending."""
    if p.name == 'freeze.json':
        data = json.loads(p.read_text()); data.pop('authorization', None)
        return (json.dumps(data, indent=2) + '\n').encode()
    return p.read_bytes()


def zip_tree(src, dst, keep=lambda p: True):
    """Deterministic archive: sorted names, fixed timestamps."""
    dst = OUT / dst
    dst.parent.mkdir(parents=True, exist_ok=True)
    files = sorted(p for p in src.rglob('*') if p.is_file() and p.name != '.DS_Store' and keep(p))
    with zipfile.ZipFile(dst, 'w', zipfile.ZIP_DEFLATED, compresslevel=9) as z:
        for p in files:
            info = zipfile.ZipInfo(str(p.relative_to(src.parent)), date_time=(1980, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o644 << 16
            z.writestr(info, public_bytes(p), compresslevel=9)
    return len(files)


def portfolio():
    factors = pd.read_csv(ROOT / 'data/v2/analysis/csit_cost_audit/factors.csv', index_col=0, parse_dates=True)
    (OUT / 'portfolio').mkdir(parents=True, exist_ok=True)
    factors.loc['2006-01-01':'2025-12-31'].to_csv(OUT / 'portfolio/factors.csv')
    for g in ['core', 'holdout']:
        copy(BASE / f'publication_audit_v1/{g}_original_returns.csv', f'portfolio/{g}_returns.csv')
        copy(BASE / f'signal_risk_v1/{g}_daily_returns.csv', f'portfolio/{g}_controls_returns.csv')
        copy(BASE / f'publication_audit_v1/{g}_charged_turnover.csv', f'portfolio/{g}_controls_turnover.csv')
        copy(BASE / f'signal_risk_v1/{g}_targets.npz', f'portfolio/{g}_controls_weights.npz')
        copy(BASE / f'relative_spec_v1/{g}_returns.csv', f'portfolio/{g}_relative_returns.csv')
        copy(BASE / f'signal_risk_v1/{g}_signal_panel.csv', f'signal/{g}_signal_panel.csv')
        copy(BASE / f'publication_audit_v1/{g}_matched_metrics.csv', f'portfolio/saved/{g}_matched_metrics.csv')
        copy(BASE / f'random_views_matched_scale_v1/{g}_runs.csv', f'portfolio/saved/{g}_random_views_61_4bps_runs.csv')
        raw = (BASE / f'matched_controls_v1/{g}_daily_returns.csv').read_bytes()
        with open(OUT / f'portfolio/{g}_matched_returns.csv.gz', 'wb') as fh, gzip.GzipFile(fileobj=fh, mode='wb', mtime=0, compresslevel=9) as gz:
            gz.write(raw)
    for name in ['metrics.csv', 'comparisons.csv', 'costs.csv']:
        copy(BASE / 'publication_audit_v1' / name, f'portfolio/saved/{name}')
    copy(BASE / 'random_views_comparison_v1/primary_table.csv', 'portfolio/saved/primary_table.csv')
    copy(BASE / 'signal_risk_v1/factor_regressions.csv', 'portfolio/saved/factor_regressions.csv')
    copy(BASE / 'signal_risk_v1/results.json', 'portfolio/saved/signal_results.json')
    for name in ['permutations.json', 'random_views_ensemble.json', 'factor_loadings.json', 'view_scale.json']:
        copy(BASE / 'reviewer_checks_v1' / name, f'portfolio/saved/{name}')
    copy(BASE / 'relative_spec_v1/portfolios.json', 'portfolio/saved/relative_portfolios.json')
    copy(BASE / 'relative_spec_v1/distances.json', 'portfolio/saved/relative_distances.json')
    copy(BASE / 'random_views_matched_scale_v1/ensemble.json', 'portfolio/saved/random_views_61_4bps.json')
    for ext in ['png', 'pdf']:
        copy(ROOT / f'paper/informatica/v5_ua/figures/fig2_wealth.{ext}', f'figures/fig2_wealth.{ext}')
        copy(ROOT / f'paper/informatica/v5_ua/figures/fig3_intervals_eight.{ext}', f'figures/fig3_intervals_eight.{ext}')


def experiments():
    from scripts.run_backtest import load_all_prices, load_universe
    from src.optimization.covariance import rolling_covariance
    from src.optimization.black_litterman import compute_prior
    from scripts.v2.analyze_informatica_text_ablation import allocate as allocate_neutral
    from scripts.v2.analyze_informatica_portfolio_masking import allocate as allocate_masking
    universe = load_universe(str(ROOT / 'config/universe.yaml'))
    prices = load_all_prices(ROOT / 'data/raw', universe['core'] + universe['holdout'])
    cases, records, slices, design = [], [], [], {}
    for label, prep, suffix in SETS:
        manifest = json.loads((BASE / prep / 'manifest.json').read_text())
        design[label] = dict(dates=manifest['dates'], model=manifest.get('model'), missing=manifest.get('missing'))
        rec = {}
        for exp in ARMS:
            for p in sorted((BASE / f'{exp}{suffix}').glob('[0-9][0-9][0-9][0-9]_*.json')):
                r = json.loads(p.read_text()); j = r['job']; resp = r['response']
                assert r['valid'] and not r['fatal'], p
                rec[exp, j['case_id'], j['condition'], j['repeat']] = r['parsed']
                records.append(dict(date_set=label, experiment=exp, case_id=j['case_id'], condition=j['condition'], repeat=j['repeat'],
                                    view_bps=r['parsed']['view_bps'], confidence=r['parsed']['confidence'], reasoning=r['parsed'].get('reasoning'),
                                    generation_id=resp['id'], model=resp['model'], provider=resp.get('provider'), completed_utc=r['completed_utc'],
                                    cost_usd=r['cost'], prompt_tokens=resp['usage']['prompt_tokens'], completion_tokens=resp['usage']['completion_tokens']))
        for c in manifest['cases']:
            cases.append(dict(date_set=label, **c))
        for date in manifest['dates']:
            for group in ['core', 'holdout']:
                sub = [c for c in manifest['cases'] if c['date'] == date and c['group'] == group]
                names = universe[group]
                cov = rolling_covariance(prices[names], pd.Timestamp(date), lookback=252)
                prior = compute_prior(cov, np.ones(len(names)) / len(names), 2.5)
                weights = {}
                for exp, arms in ARMS.items():
                    alloc = allocate_neutral if exp == 'ablation' else allocate_masking
                    for arm in arms:
                        weights[f'{exp}/{arm}'] = [alloc(sub, {c['case_id']: rec[exp, c['case_id'], arm, r] for c in sub}, names, cov, prior)[0].tolist() for r in (1, 2, 3)]
                slices.append(dict(date_set=label, date=date, group=group, cases=len(sub), tickers=names, weights=weights))
        zip_tree(BASE / prep, f'experiments/inputs_{label}_dates.zip')
        for exp in ARMS:
            zip_tree(BASE / f'{exp}{suffix}', f'experiments/raw_{exp}_{label}_dates.zip')
    write_json('experiments/design.json', design)
    write_json('experiments/cases.json', cases)
    write_json('experiments/records.json', records)
    write_json('experiments/weights.json', slices)
    for name in ['llm_dates_analysis.json', 'llm_experiments_analysis.json', 'llm_rank_analysis.json']:
        copy(BASE / name, f'experiments/saved/{name}')
    print('experiments:', len(cases), 'cases,', len(records), 'records,', len(slices), 'slices', flush=True)


def extraction():
    for p in sorted((ROOT / 'data/v2/gold_standard').glob('*.json')):
        copy(p, f'extraction/gold_standard/{p.name}')
    n = zip_tree(ROOT / 'data/v2/model_selection', 'extraction/model_events.zip', keep=lambda p: p.suffix == '.json')
    copy(BASE / 'table1_all_filings_v1/table1.json', 'extraction/saved/table1.json')
    a = zip_tree(ROOT / 'data/v2/extracted_v2', 'corpus/extracted_facts_gemini.zip', keep=lambda p: p.suffix == '.json')
    b = zip_tree(ROOT / 'data/v2/views_v2', 'corpus/views_gemini.zip', keep=lambda p: p.suffix == '.json')
    (OUT / 'corpus/views_summary.csv').write_bytes((ROOT / 'data/v2/views_v2/views_summary.csv').read_bytes().replace(b'\r\n', b'\n'))  # LF line endings
    print('extraction:', n, 'model files,', a, 'extraction files,', b, 'view files', flush=True)


def source():
    for p in sorted(HERE.glob('*.py')):
        copy(p, f'source/scripts/v2/v5_gemini/{p.name}')
    for name in ['portfolio_protocol', 'reanalyze_informatica_returns', 'analyze_informatica_text_ablation', 'analyze_informatica_portfolio_masking']:
        copy(ROOT / f'scripts/v2/{name}.py', f'source/scripts/v2/{name}.py')
    for name in ['run_backtest', 'extract_facts', 'generate_views']:
        copy(ROOT / f'scripts/{name}.py', f'source/scripts/{name}.py')
    for p in sorted((ROOT / 'src').rglob('*.py')):
        copy(p, f'source/{p.relative_to(ROOT)}')
    copy(HERE / 'verify_v5_package.py', 'verify.py')
    copy(HERE / 'V5_PACKAGE_README.md', 'README.md')
    (OUT / '.gitattributes').write_text('# keep bytes as published so that SHA256.json holds on every platform\n* -text\n')
    (OUT / 'requirements.txt').write_text('numpy==2.4.1\npandas==2.3.3\nscipy==1.17.0\nstatsmodels==0.14.6\nrapidfuzz==3.14.5\n')


def finish():
    for p in sorted(OUT.rglob('*')):
        if p.is_file() and p.suffix in {'.json', '.csv', '.py', '.md', '.txt'}:
            text = p.read_text(errors='ignore')
            for bad in FORBIDDEN:
                assert not re.search(bad, text), (bad, p)
    files = sorted(p for p in OUT.rglob('*') if p.is_file() and p.name not in {'SHA256.json', '.DS_Store'})
    manifest = {str(p.relative_to(OUT)): hashlib.sha256(p.read_bytes()).hexdigest() for p in files}
    (OUT / 'SHA256.json').write_text(json.dumps(manifest, indent=1) + '\n')
    size = sum(p.stat().st_size for p in files)
    print(f'package: {len(files)} files, {size / 1048576:.1f} MB, largest:', flush=True)
    for p in sorted(files, key=lambda p: -p.stat().st_size)[:8]:
        print(f'  {p.stat().st_size / 1048576:6.1f} MB  {p.relative_to(OUT)}', flush=True)


def main():
    logging.disable(logging.CRITICAL)
    if OUT.exists():
        shutil.rmtree(OUT)
    OUT.mkdir(parents=True)
    portfolio(); experiments(); extraction(); source(); finish()


if __name__ == '__main__':
    main()
