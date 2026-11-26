"""Standalone offline verifier for the gemini-2.5-flash package of the article.

Reads only files of this package, calls no model and needs no price history. It checks every
SHA-256 and recomputes the numbers reported in the article from the saved returns, weights,
model answers and annotations. A reported number passes when the recomputed value rounds to it.

Run from the repository root:  python experiments/informatica_2026_v5_gemini/verify.py
"""
from pathlib import Path
from itertools import combinations
import hashlib
import json
import re
import sys
import unicodedata
import zipfile
import numpy as np
import pandas as pd
from scipy.stats import spearmanr
import statsmodels.api as sm
from rapidfuzz import fuzz

P = Path(sys.argv[1]).resolve() if len(sys.argv) > 1 else Path(__file__).resolve().parent
sys.path.insert(0, str(P / 'source/scripts/v2'))
import reanalyze_informatica_returns as paired  # noqa: E402

paired.RF = 0.0  # excess returns are passed explicitly
GROUPS = ['core', 'holdout']
CHECKED = []


def shown(value, reported, decimals, what):
    """A reported number passes when the recomputed value rounds to it."""
    assert abs(value - reported) <= 0.5 * 10 ** -decimals + 1e-9, f'{what}: recomputed {value:.6f}, reported {reported}'
    CHECKED.append(what)


def read(name):
    return pd.read_csv(P / name, index_col=0, parse_dates=True).loc[:'2025-12-31']


def metrics(r, rf):
    e = r.sub(rf, axis=0)
    wealth = (1 + r).cumprod()
    peak = wealth.cummax().clip(lower=1)
    return pd.DataFrame({'cagr': wealth.iloc[-1] ** (252 / len(r)) - 1, 'volatility': r.std() * np.sqrt(252),
                         'sharpe': e.mean() / e.std() * np.sqrt(252), 'max_drawdown': (wealth / peak - 1).min()})


# ---------------------------------------------------------------- 1. integrity
manifest = json.loads((P / 'SHA256.json').read_text())
for name, digest in manifest.items():
    assert hashlib.sha256((P / name).read_bytes()).hexdigest() == digest, name
print(f'1. integrity: {len(manifest)} files match SHA256.json', flush=True)

# ---------------------------------------------------------------- 2. portfolios (Tables 4 and 5)
TABLE4 = {  # variant: CAGR %, Sharpe, max drawdown % (core, holdout)
    'bl_llm_tilt_pos': ((15.67, 12.66), (0.639, 0.541), (-62.23, -63.58)),
    'bl_llm_tilt': ((11.88, 9.48), (0.565, 0.462), (-51.56, -63.37)),
    'equal_weight': ((12.19, 10.66), (0.581, 0.522), (-52.55, -56.58)),
    'mvo': ((13.62, 8.82), (0.619, 0.426), (-43.08, -56.60)),
    'random_views': ((5.68, 8.65), (0.327, 0.508), (-39.16, -37.30)),
    'bl_llm': ((6.42, 8.34), (0.373, 0.488), (-38.50, -41.21)),
}
RELATIVE = ((15.46, 12.79), (0.615, 0.534), (-64.23, -65.00))
VOLATILITY = {'bl_llm_tilt_pos': (25.19, 25.30), 'equal_weight': (20.65, 20.82)}
CONTROL = {'cagr': (15.44, 12.84), 'sharpe': (0.613, 0.535)}
PERMUTATIONS = {'eligible_shuffle': ((0.626, 0.613, 0.639), (0.538, 0.523, 0.552)), 'full_shuffle': ((0.618, 0.565, 0.684), (0.513, 0.467, 0.576))}
factors = pd.read_csv(P / 'portfolio/factors.csv', index_col=0, parse_dates=True)
frames = {}
for gi, g in enumerate(GROUPS):
    raw = read(f'portfolio/{g}_returns.csv')
    rf = factors.RF.reindex(raw.index)
    assert rf.notna().all()
    m = metrics(raw, rf)
    for name, (cagr, sharpe, mdd) in TABLE4.items():
        shown(100 * m.loc[name, 'cagr'], cagr[gi], 2, f'Table 4 CAGR {name} {g}')
        shown(m.loc[name, 'sharpe'], sharpe[gi], 3, f'Table 4 Sharpe {name} {g}')
        shown(100 * m.loc[name, 'max_drawdown'], mdd[gi], 2, f'Table 4 drawdown {name} {g}')
    for name, vol in VOLATILITY.items():
        shown(100 * m.loc[name, 'volatility'], vol[gi], 2, f'volatility {name} {g}')
    shown(100 * (m.loc['bl_llm_tilt_pos', 'cagr'] - m.loc['equal_weight', 'cagr']), (3.48, 2.00)[gi], 2, f'CAGR advantage over EW {g}')
    controls = read(f'portfolio/{g}_controls_returns.csv')
    assert controls.index.equals(raw.index) and np.max(np.abs(controls.real - raw.bl_llm_tilt_pos)) < 1e-12
    c = metrics(controls, rf)
    shown(100 * c.loc['prior_only', 'cagr'], CONTROL['cagr'][gi], 2, f'control CAGR {g}')
    shown(c.loc['prior_only', 'sharpe'], CONTROL['sharpe'][gi], 3, f'Table 5 control Sharpe {g}')
    relative = read(f'portfolio/{g}_relative_returns.csv')
    r = metrics(relative, factors.RF.reindex(relative.index)).loc['rel_pos']
    shown(100 * r.cagr, RELATIVE[0][gi], 2, f'relative specification CAGR {g}')
    shown(r.sharpe, RELATIVE[1][gi], 3, f'relative specification Sharpe {g}')
    shown(100 * r.max_drawdown, RELATIVE[2][gi], 2, f'relative specification drawdown {g}')
    matched = read(f'portfolio/{g}_matched_returns.csv.gz')
    assert matched.index.equals(raw.index)
    ms = metrics(matched, rf).sharpe
    for scheme, expected in PERMUTATIONS.items():
        s = ms.filter(like=scheme).to_numpy()
        assert len(s) == 100
        for value, reported, label in zip([np.median(s), np.quantile(s, .05), np.quantile(s, .95)], expected[gi], ['median', '5th percentile', '95th percentile']):
            shown(value, reported, 3, f'Table 5 {scheme} {label} {g}')
    ensemble = json.loads((P / 'portfolio/saved/random_views_ensemble.json').read_text())[g]
    assert ensemble['sharpe_p05'] <= m.loc['bl_llm', 'sharpe'] <= ensemble['sharpe_p95'], 'BL-Filing MVO outside the Random Views spread'
    frames[g] = dict(raw=raw, rf=rf, controls=controls, matched=matched)
print('2. portfolios: Tables 4 and 5 reproduced from saved daily returns', flush=True)

# ---------------------------------------------------------------- 3. bootstrap intervals and tests
PAIRS = [('bl_llm_tilt_pos', 'equal_weight'), ('bl_llm_tilt_pos', 'mvo'), ('bl_llm_tilt', 'bl_llm'), ('bl_llm_tilt_pos', 'random_views')]
rows = []
for gi, g in enumerate(GROUPS):
    raw, rf = frames[g]['raw'][paired.NAMES], frames[g]['rf']
    e = raw.sub(rf, axis=0)
    boot = paired.block_sharpes(e.to_numpy(), 21, 10000, 20261116 + gi * 1000 + 21)
    for a, b in PAIRS:
        ia, ib = raw.columns.get_loc(a), raw.columns.get_loc(b)
        ci = np.quantile(boot[:, ia] - boot[:, ib], [.025, .975])
        rows.append(dict(group=g, a=a, b=b, difference=float(np.sqrt(252) * (e[a].mean() / e[a].std() - e[b].mean() / e[b].std())),
                         low=float(ci[0]), high=float(ci[1]), **paired.hac_mean((raw[a] - raw[b]).to_numpy(), 21)))
tests = pd.DataFrame(rows)
tests['p_holm'] = paired.holm(tests.p_raw.to_numpy())
saved = pd.read_csv(P / 'portfolio/saved/primary_table.csv').merge(tests, on=['group', 'a', 'b'], suffixes=('_saved', ''))
assert len(saved) == 8
for col in ['difference', 'low', 'high', 'p_raw', 'p_holm', 'annualized_mean_difference']:
    np.testing.assert_allclose(saved[col], saved[col + '_saved'], rtol=1e-9, atol=1e-11)
for gi, g in enumerate(GROUPS):
    row = tests[(tests.group == g) & (tests.b == 'equal_weight')].iloc[0]
    for value, reported, label in zip([row.difference, row.low, row.high, row.p_holm], [(0.058, 0.019), (-0.060, -0.085), (0.165, 0.114), (0.071, 0.328)], ['difference', 'lower', 'upper', 'Holm p']):
        shown(value, reported[gi], 3, f'Sharpe difference to EW {label} {g}')
    f = frames[g]
    extra = f['controls'].copy()
    for scheme in ['full_shuffle', 'eligible_shuffle']:
        extra[scheme + '_mean'] = f['matched'].filter(like=scheme).mean(axis=1)
    e = extra.sub(f['rf'], axis=0)
    boot = paired.block_sharpes(e.to_numpy(), 21, 10000, 20262116 + gi * 100 + 21)
    ia, ib = extra.columns.get_loc('real'), extra.columns.get_loc('prior_only')
    ci = np.quantile(boot[:, ia] - boot[:, ib], [.025, .975])
    diff = float(np.sqrt(252) * (e.real.mean() / e.real.std() - e.prior_only.mean() / e.prior_only.std()))
    for value, reported, label in zip([diff, ci[0], ci[1]], [(0.026, 0.006), (-0.053, -0.060), (0.103, 0.068)], ['difference', 'lower', 'upper']):
        shown(value, reported[gi], 3, f'Sharpe difference to control {label} {g}')
print('3. statistics: eight comparisons, Holm adjustment and control intervals reproduced (10,000 block-bootstrap draws)', flush=True)

# ---------------------------------------------------------------- 4. turnover and costs
for gi, g in enumerate(GROUPS):
    extra = frames[g]['controls']
    charges = read(f'portfolio/{g}_controls_turnover.csv')
    turnover = charges.sum() / (len(extra) / 252)
    shown(turnover['real'], (2.09, 2.18)[gi], 2, f'turnover BL-Filing+ {g}')
    shown(turnover['equal_weight'], (0.37, 0.36)[gi], 2, f'turnover EW {g}')
    if g == 'core':
        for bp, real, ew in [(5, 15.79, 12.21), (10, 15.67, 12.19), (20, 15.43, 12.15)]:
            net = metrics(extra + (.001 - bp / 10000) * charges, frames[g]['rf'])
            shown(100 * net.loc['real', 'cagr'], real, 2, f'CAGR BL-Filing+ at {bp} bps')
            shown(100 * net.loc['equal_weight', 'cagr'], ew, 2, f'CAGR EW at {bp} bps')
print('4. costs: turnover and CAGR at 5, 10 and 20 bps reproduced', flush=True)

# ---------------------------------------------------------------- 5. text and name experiments
design = json.loads((P / 'experiments/design.json').read_text())
cases = json.loads((P / 'experiments/cases.json').read_text())
records = json.loads((P / 'experiments/records.json').read_text())
answers = {(r['date_set'], r['experiment'], r['case_id'], r['condition'], r['repeat']): r['view_bps'] for r in records}
assert len(answers) == len(records) == 7485 and len(cases) == 499
assert sum(r['experiment'] == 'ablation' for r in records) == 4491 and sum(r['experiment'] == 'masking' for r in records) == 2994
assert {r['model'] for r in records} == {'google/gemini-2.5-flash'}
CONTRASTS = {'removal': ('ablation', 'real_text', 'no_text'), 'replacement': ('ablation', 'real_text', 'shuffled_text'), 'masking': ('masking', 'original', 'anonymized')}


def per_case(a, b):
    wa = np.mean(np.stack([np.abs(a[:, i] - a[:, j]) for i, j in combinations(range(3), 2)]), axis=0)
    wb = np.mean(np.stack([np.abs(b[:, i] - b[:, j]) for i, j in combinations(range(3), 2)]), axis=0)
    cross = np.abs(a[:, :, None] - b[:, None, :]).mean((1, 2))
    return np.abs(a.mean(1) - b.mean(1)), cross - (wa + wb) / 2


def interval(x, rng):
    idx = rng.integers(len(x), size=(5000, len(x)))
    return np.quantile(x[idx].mean(1), [.025, .975])


rng = np.random.default_rng(20261125)
pooled = {}
for label in ['original', 'extra']:
    for date in design[label]['dates']:
        for g in GROUPS:
            sub = [c for c in cases if c['date_set'] == label and c['date'] == date and c['group'] == g]
            for contrast, (exp, a, b) in CONTRASTS.items():
                va = np.array([[answers[label, exp, c['case_id'], a, k] for k in (1, 2, 3)] for c in sub])
                vb = np.array([[answers[label, exp, c['case_id'], b, k] for k in (1, 2, 3)] for c in sub])
                absd, excess = per_case(va, vb)
                pooled.setdefault((date, contrast), []).append((absd, excess))
                interval(excess, rng)  # same random stream as the original analysis
by_date = {}
for (date, contrast), parts in sorted(pooled.items()):
    excess = np.concatenate([p[1] for p in parts])
    by_date[date, contrast] = (float(excess.mean()), interval(excess, rng))
VIEWS = {'removal': (28.17, 25.09, 22.42, 27.97), 'replacement': (33.24, 29.44, 26.02, 32.90), 'masking': (10.28, 6.84, 5.50, 8.29)}
reference = json.loads((P / 'experiments/saved/llm_dates_analysis.json').read_text())
for contrast, reported in VIEWS.items():
    absd = np.concatenate([p[0] for (d, c), parts in pooled.items() if c == contrast for p in parts])
    excess = np.concatenate([p[1] for (d, c), parts in pooled.items() if c == contrast for p in parts])
    ci = interval(excess, rng)
    assert len(absd) == 499
    for value, target, label in zip([absd.mean(), excess.mean(), ci[0], ci[1]], reported, ['mean absolute change', 'excess over repeats', 'interval lower', 'interval upper']):
        shown(value, target, 2, f'views {contrast} {label}')
    np.testing.assert_allclose(ci, reference['all_dates'][contrast]['view_excess_ci95'], rtol=1e-12)
    assert all(by_date[date, contrast][1][0] > 0 for date in sorted({d for d, _ in pooled})), f'{contrast}: an interval covers zero'
slices = json.loads((P / 'experiments/weights.json').read_text())
saved_slices = {(s['date'], s['group']): s for s in reference['slices']}
table3 = []
for s in slices:
    row = dict(date=s['date'], group=s['group'])
    for contrast, (exp, a, b) in CONTRASTS.items():
        wa, wb = np.array(s['weights'][f'{exp}/{a}']), np.array(s['weights'][f'{exp}/{b}'])
        np.testing.assert_allclose(wa.sum(1), 1, atol=1e-9)
        within = np.mean([np.abs(x[i] - x[j]).sum() / 2 for x in (wa, wb) for i, j in combinations(range(3), 2)])
        row[contrast], row[contrast + '_repeats'] = float(np.abs(wa.mean(0) - wb.mean(0)).sum() / 2), float(within)
        ref = saved_slices[s['date'], s['group']]
        np.testing.assert_allclose([row[contrast], within], [ref[f'{contrast}_weight_distance'], ref[f'{contrast}_weight_between_repeats']], rtol=1e-9, atol=1e-12)
    table3.append(row)
table3 = pd.DataFrame(table3)
for value, reported, label in [(table3.removal.min(), 7.65, 'removal min'), (table3.removal.max(), 28.43, 'removal max'), (table3.replacement.min(), 8.23, 'replacement min'),
                               (table3.replacement.max(), 31.61, 'replacement max'), (table3[['removal_repeats', 'replacement_repeats']].min().min(), 1.22, 'repeats min'),
                               (table3[['removal_repeats', 'replacement_repeats']].max().max(), 4.92, 'repeats max'), (table3.masking.min(), 1.16, 'masking min'), (table3.masking.max(), 14.18, 'masking max')]:
    shown(100 * value, reported, 2, f'Table 3 {label}')
assert (table3.removal / table3.removal_repeats).min() >= 2.5 and (table3.replacement / table3.replacement_repeats).min() >= 2.5
print('5. experiments: 7,485 answers; view changes, intervals and Table 3 weight distances reproduced', flush=True)

# ---------------------------------------------------------------- 6. extraction quality (Table 1) and quote rate
CHAR_MAP = str.maketrans({'‘': "'", '’': "'", '‚': "'", '‛': "'", '“': '"', '”': '"', '„': '"', '‟': '"',
                          '–': '-', '—': '-', '‒': '-', '―': '-', '−': '-', ' ': ' ', ' ': ' ', ' ': ' ', ' ': ' ',
                          '­': None, '​': None})


def normalize(text):
    if not text:
        return ''
    return re.sub(r'\s+', ' ', unicodedata.normalize('NFKC', text).translate(CHAR_MAP).lower()).strip()


def similarity(a, b):
    da, db = normalize(a.get('description', '')), normalize(b.get('description', ''))
    qa, qb = normalize(a.get('source_quote', '')), normalize(b.get('source_quote', ''))
    return max(fuzz.token_set_ratio(da, db) if da and db else 0, fuzz.partial_ratio(qa, qb) if qa and qb else 0)


def matches(model_events, gold_events, threshold=60.0):
    pairs = sorted(((similarity(m, g), i, j) for i, m in enumerate(model_events) for j, g in enumerate(gold_events)), reverse=True)
    used_m, used_g = set(), set()
    for score, i, j in pairs:
        if score >= threshold and i not in used_m and j not in used_g:
            used_m.add(i); used_g.add(j)
    return len(used_m)


TABLE1 = {'google_gemini-2.5-flash': (0.36, 0.55, 0.44), 'google_gemini-2.5-flash-lite': (0.32, 0.63, 0.42), 'anthropic_claude-haiku-4.5': (0.30, 0.57, 0.40),
          'qwen_qwen3.8-27b': (0.24, 0.64, 0.35), 'deepseek_deepseek-chat-v3.1': (0.24, 0.63, 0.35), 'meta-llama_llama-4-maverick': (0.17, 0.63, 0.27),
          'openai_gpt-4o-mini': (0.10, 0.72, 0.18), 'z-ai_glm-5.3-flash': (0.10, 0.57, 0.17)}
PROCESSED = {'qwen_qwen3.8-27b': 72, 'z-ai_glm-5.3-flash': 26}  # per cent of the 90 filings, section 3.3
gold = {}
for path in sorted((P / 'extraction/gold_standard').glob('[0-9]*.json')):
    doc = json.loads(path.read_text())
    gold[doc['id']] = doc
ids = sorted(gold)
assert len(ids) == 90 and sum(len(d['events']) for d in gold.values()) == 850
saved_table = json.loads((P / 'extraction/saved/table1.json').read_text())
draws = np.random.default_rng(20261125).integers(len(ids), size=(5000, len(ids)))
with zipfile.ZipFile(P / 'extraction/model_events.zip') as z:
    for slug, (recall, precision, f1) in TABLE1.items():
        counts = {i: [0, len(gold[i]['events']), 0] for i in ids}  # matched, annotated, extracted
        processed = 0
        for name in z.namelist():
            if name.split('/')[-2] != slug or not name.split('/')[-1][0].isdigit():
                continue
            rec = json.loads(z.read(name))
            facts = rec.get('facts')
            if rec['doc_id'] not in gold or not facts:
                continue  # a filing the model failed on counts as no events found
            processed += 1
            events = facts.get('key_events', [])
            counts[rec['doc_id']][0] = matches(events, gold[rec['doc_id']]['events']); counts[rec['doc_id']][2] = len(events)
        a = np.array([counts[i] for i in ids], dtype=float)
        tp, total, found = (int(x) for x in a.sum(axis=0))
        saved = saved_table[slug]
        assert (tp, total, found, processed) == (saved['tp'], saved['gold'], saved['extracted'], saved['processed']), (slug, tp, total, found, processed)
        r, p = tp / total, tp / found
        shown(r, recall, 2, f'Table 1 recall {slug}'); shown(p, precision, 2, f'Table 1 precision {slug}'); shown(2 * r * p / (r + p), f1, 2, f'Table 1 F1 {slug}')
        if slug in PROCESSED:
            shown(100 * processed / len(ids), PROCESSED[slug], 0, f'share of filings processed {slug}')
        if slug == 'google_gemini-2.5-flash':
            assert processed == len(ids)
            b = a[draws].sum(axis=1)
            for values, reported, label in [(b[:, 0] / b[:, 1], (0.31, 0.42), 'recall'), (b[:, 0] / b[:, 2], (0.50, 0.61), 'precision')]:
                low, high = np.quantile(values, [.025, .975])
                shown(low, reported[0], 2, f'Table 1 {label} interval, lower'); shown(high, reported[1], 2, f'Table 1 {label} interval, upper')
grounded = checked = files = 0
with zipfile.ZipFile(P / 'corpus/extracted_facts_gemini.zip') as z:
    for name in z.namelist():
        summary = json.loads(z.read(name)).get('grounding') or {}
        grounded += summary.get('grounded', 0); checked += summary.get('total_facts', 0); files += 1
assert (files, grounded, checked) == (9100, 138632, 141480)
shown(100 * grounded / checked, 98.0, 1, 'share of facts with a located quote')
with zipfile.ZipFile(P / 'corpus/views_gemini.zip') as z:
    assert sum(n.endswith('.json') for n in z.namelist()) == 8001
print('6. extraction: Table 1 recomputed from annotations and model answers; quote rate 138,632 of 141,480', flush=True)

# ---------------------------------------------------------------- 7. information coefficient and factor regressions
for gi, g in enumerate(GROUPS):
    panel = pd.read_csv(P / f'signal/{g}_signal_panel.csv')
    ic = np.array([spearmanr(a.view_bps, a.outcome).statistic for _, a in panel.groupby('date') if len(a) >= 10 and a.view_bps.nunique() > 1 and a.outcome.nunique() > 1])
    assert len(ic) == 79
    fit = sm.OLS(ic, np.ones((len(ic), 1))).fit(cov_type='HAC', cov_kwds={'maxlags': 4, 'use_correction': True}, use_t=False)
    low, high = fit.conf_int()[0]
    for value, reported, label in zip([fit.params[0], low, high], [(-0.018, -0.015), (-0.054, -0.050), (0.018, 0.021)], ['mean', 'lower', 'upper']):
        shown(value, reported[gi], 3, f'IC {label} {g}')
    f = frames[g]
    data = f['controls'].join(factors, how='inner')
    x = sm.add_constant(data[['Mkt-RF', 'SMB', 'HML', 'Mom']])
    fit = sm.OLS(data.real - data.prior_only, x).fit(cov_type='HAC', cov_kwds={'maxlags': 21, 'use_correction': True}, use_t=False)
    shown(100 * 252 * fit.params['const'], (0.39, 0.15)[gi], 2, f'alpha of the return difference {g}')
    shown(fit.pvalues['const'], (0.692, 0.854)[gi], 3, f'alpha p-value {g}')
    load = {arm: sm.OLS(data[arm] - data.RF, x).fit().params['Mkt-RF'] for arm in ['real', 'prior_only', 'equal_weight']}
    assert 1.045 <= min(load['real'], load['prior_only']) and max(load['real'], load['prior_only']) < 1.115 and 0.925 <= load['equal_weight'] < 0.945, load
print('7. signal: information coefficient, alpha of the return difference and market loadings reproduced', flush=True)

print(f'PASS: {len(manifest)} files, {len(CHECKED)} reported numbers reproduced offline.', flush=True)
