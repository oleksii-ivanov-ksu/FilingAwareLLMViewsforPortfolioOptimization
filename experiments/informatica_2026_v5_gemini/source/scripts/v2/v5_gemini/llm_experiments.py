"""V5 (gemini-2.5-flash) text-ablation and name-masking experiments.

Same design as the Grok 4.3 diagnostics (prepare_informatica_portfolio_masking.py,
prepare_informatica_text_ablation.py and their runners/analyses), rebuilt on the
v2 two-stage data: facts from data/v2/extracted_v2, saved views from data/v2/views_v2.
Nothing under informatica_revision/ or the frozen v1 folders is written.

  prepare             build and freeze all prompts (no network)
  run --experiment X  X = masking | ablation; dry run unless --execute is given
  analyze             offline analysis of the saved responses
"""
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
from collections import Counter
from datetime import datetime, timezone
import argparse, csv, hashlib, json, os, random, re, sys, threading, time, urllib.request
import numpy as np
import pandas as pd
import yaml

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
from src.reasoning.input_builder import InputBuilder
from src.reasoning.prompts import REASONER_SYSTEM_PROMPT, format_user_prompt
from scripts.v2.prepare_informatica_pilot import summary, differences
from scripts.v2.prepare_informatica_portfolio_masking import identity_mask
from scripts.v2.prepare_informatica_text_ablation import split_prompt
from scripts.v2.run_informatica_pilot import valid_response

BASE = ROOT / 'data/v2/analysis/informatica_v5_gemini'
PREP = BASE / 'llm_inputs_v1'
SUFFIX = '_gemini25flash_v1'
ANALYSIS = 'llm_experiments_analysis.json'
VIEWS = ROOT / 'data/v2/views_v2'
FACTS = ROOT / 'data/v2/extracted_v2'
DATES = ['2015-09-30', '2025-09-30']
# Extension requested after review (2026-11-25): more September quarter-ends, fixed before any output was seen.
EXTRA_DATES = ['2010-09-30', '2020-09-30', '2023-09-30']
MODEL = 'google/gemini-2.5-flash'
CONFIG = {'model': MODEL, 'temperature': .3, 'max_tokens': 2000, 'response_format': {'type': 'json_object'}}
ARMS = {'masking': ['original', 'anonymized'], 'ablation': ['real_text', 'no_text', 'shuffled_text']}
BUDGET = 10.0


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def dump(path, obj):
    path.write_text(json.dumps(obj, indent=2, ensure_ascii=False) + '\n')


def prepare():
    if PREP.exists():
        raise SystemExit('Refusing to overwrite llm_inputs_v1')
    universe = yaml.safe_load((ROOT / 'config/universe.yaml').read_text())['universe']
    companies = {r['Symbol']: r for r in csv.DictReader((ROOT / 'data/constituents.csv').open())}
    views = pd.read_csv(VIEWS / 'views_summary.csv', parse_dates=['view_date'])
    archive = {}
    for p in sorted(VIEWS.glob('*/*.json')):
        d = json.loads(p.read_text())
        key = (d['ticker'], d['view_date'], d['fiscal_period'])
        assert key not in archive, key
        archive[key] = (p, d)
    builder = InputBuilder(FACTS, ROOT / 'data/raw', ROOT / 'data/constituents.csv')
    cases, missing, prompts = [], [], {}
    for date in DATES:
        for group in ['core', 'holdout']:
            for ticker in universe[group]:
                available = views[(views.ticker == ticker) & (views.view_date <= date)]
                if available.empty or (pd.Timestamp(date) - available.iloc[-1].view_date).days > 120:
                    missing.append({'date': date, 'group': group, 'ticker': ticker,
                                    'policy': 'no view within 120 days; stock stays in the 50-stock universe without a view'})
                    continue
                row = available.iloc[-1]
                path, saved = archive[(ticker, str(row.view_date.date()), row.fiscal_period)]
                trig = saved['triggered_by']
                fact = FACTS / ticker / f"{trig['filing_type']}_{trig['filing_date']}.json"
                inp = builder.build_input_for_filing(ticker, json.loads(fact.read_text()))
                assert inp is not None and str(inp.view_date) == saved['view_date'], (ticker, date)
                diff = differences(saved['inputs'], summary(inp))
                assert not diff, (ticker, date, diff)
                prompt = format_user_prompt(inp)
                masked, changes = identity_mask(prompt, ticker, companies[ticker]['Security'])
                assert changes
                cid = f'W{len(cases) + 1:03d}'
                prompts[cid] = {'original': prompt, 'anonymized': masked}
                cases.append({'case_id': cid, 'date': date, 'group': group, 'ticker': ticker,
                              'view_date': saved['view_date'], 'fiscal_period': saved['fiscal_period'],
                              'sentiment': row.sentiment if pd.notna(row.sentiment) else None,
                              'source_view': str(path.relative_to(ROOT)), 'source_fact': str(fact.relative_to(ROOT)),
                              'identity_spans': len(changes)})
    # Text ablation: one fixed within-slice derangement, same procedure and seed as the Grok design.
    rng = random.Random(20261117)
    donor = {}
    for date in DATES:
        for group in ['core', 'holdout']:
            ids = sorted(c['case_id'] for c in cases if c['date'] == date and c['group'] == group)
            for _ in range(10000):
                perm = rng.sample(ids, len(ids))
                if all(a != b for a, b in zip(ids, perm)):
                    break
            else:
                raise AssertionError('No derangement')
            donor.update(dict(zip(ids, perm)))
    PREP.mkdir(parents=True)
    system = {'role': 'system', 'content': REASONER_SYSTEM_PROMPT}
    for c in cases:
        cid = c['case_id']
        folder = PREP / 'cases' / cid
        folder.mkdir(parents=True)
        for arm in ARMS['masking']:
            dump(folder / f'masking_{arm}.json', [system, {'role': 'user', 'content': prompts[cid][arm]}])
        prefix, true_text, financial = split_prompt([system, {'role': 'user', 'content': prompts[cid]['original']}])
        prefix = f"Generate an investment view for {c['ticker']} as of {c['date']}.\n" + prefix.split('\n', 1)[1]
        donor_text = split_prompt([system, {'role': 'user', 'content': prompts[donor[cid]]['original']}])[1]
        for text in [true_text, donor_text]:
            filed = re.findall(r'filed (\d{4}-\d{2}-\d{2})', text)
            assert filed and all(d <= c['date'] for d in filed)
        for arm, block in {'real_text': true_text, 'no_text': '', 'shuffled_text': donor_text}.items():
            dump(folder / f'ablation_{arm}.json', [system, {'role': 'user', 'content': prefix + block + financial}])
        c['donor_case_id'] = donor[cid]
    schedules = {}
    for exp, seed in [('masking', 20261116), ('ablation', 20261117)]:
        jobs = [{'case_id': c['case_id'], 'condition': arm, 'repeat': r} for c in cases for arm in ARMS[exp] for r in range(1, 4)]
        random.Random(seed).shuffle(jobs)
        schedules[exp] = [{'order': i + 1, **j} for i, j in enumerate(jobs)]
        dump(PREP / f'schedule_{exp}.json', schedules[exp])
    dump(PREP / 'manifest.json', {'dates': DATES, 'model': MODEL, 'cases': cases, 'missing': missing,
                                 'created_utc': datetime.now(timezone.utc).isoformat(),
                                 'source': 'data/v2/extracted_v2 facts, data/v2/views_v2 saved views; prompts rebuilt and checked field by field against saved inputs'})
    dump(PREP / 'checksums.json', {str(p.relative_to(PREP)): sha(p) for p in sorted(PREP.rglob('*')) if p.is_file()})
    print(json.dumps({'cases': len(cases), 'missing': missing, 'calls': {k: len(v) for k, v in schedules.items()}}, indent=2), flush=True)


def run(exp, execute, limit):
    out = BASE / f'{exp}{SUFFIX}'
    hashes = json.loads((PREP / 'checksums.json').read_text())
    for name, digest in hashes.items():
        assert sha(PREP / name) == digest, name
    schedule = json.loads((PREP / f'schedule_{exp}.json').read_text())
    frozen = {'config': CONFIG, 'input_inventory_sha256': sha(PREP / 'checksums.json'), 'budget_usd': BUDGET, 'workers': 8,
              'pricing_input': .00000125, 'pricing_output': .0000025, 'automatic_retries': 0,
              'authorization': 'User instructed on 2026-11-25 to carry out the whole gemini rework, including re-running both experiments (estimated under USD 10 in total)'}
    out.mkdir(parents=True, exist_ok=True)
    if (out / 'freeze.json').exists():
        assert json.loads((out / 'freeze.json').read_text()) == frozen
    else:
        dump(out / 'freeze.json', frozen)
        (out / 'runner.py').write_bytes(Path(__file__).read_bytes())
    print(f'{len(schedule)} jobs frozen for {exp}; execute={execute}', flush=True)
    if not execute:
        return
    cfg = yaml.safe_load((ROOT / 'config/config.yaml').read_text())
    key = os.environ.get('OPENROUTER_API_KEY') or cfg.get('openai', {}).get('api_key')
    assert key
    lock = threading.Lock()
    state = {'spent': 0., 'reserved': 0., 'completed': 0, 'stop': False}
    pending = []
    for job in schedule:
        stem = f"{job['order']:04d}_{job['case_id']}_{job['condition']}_{job['repeat']}"
        path = out / (stem + '.json')
        if path.exists():
            r = json.loads(path.read_text())
            assert not r.get('fatal'), stem
            state['spent'] += r['cost']
            state['completed'] += 1
        else:
            assert not (out / (stem + '.started')).exists(), 'Unfinished request requires audit: ' + stem
            pending.append((job, stem))
    if limit:
        pending = pending[:limit]

    def worker(item):
        job, stem = item
        file = PREP / 'cases' / job['case_id'] / f"{exp}_{job['condition']}.json"
        assert sha(file) == hashes[str(file.relative_to(PREP))]
        messages = json.loads(file.read_text())
        payload = dict(CONFIG, messages=messages)
        reserve = (sum(len(m['content'].encode('utf8')) for m in messages) + 400) * frozen['pricing_input'] + 2000 * frozen['pricing_output']
        with lock:
            if state['stop']:
                return
            if state['spent'] + state['reserved'] + reserve > BUDGET:
                state['stop'] = True
                return
            state['reserved'] += reserve
        with (out / (stem + '.started')).open('x') as f:
            f.write(datetime.now(timezone.utc).isoformat())
        record = {'job': job, 'request': payload, 'reserved_max_cost': reserve, 'valid': False, 'fatal': False, 'cost': 0.}
        started = time.monotonic()
        try:
            req = urllib.request.Request('https://openrouter.ai/api/v1/chat/completions', data=json.dumps(payload).encode(),
                                         headers={'Authorization': 'Bearer ' + key, 'Content-Type': 'application/json'})
            with urllib.request.urlopen(req, timeout=120) as response:
                data = json.load(response)
            record['response'] = data
            record['parsed'] = valid_response(data)
            record['valid'] = record['parsed'] is not None
            cost = data.get('usage', {}).get('cost')
            record['cost'] = float(cost or 0)
            record['fatal'] = cost is None or data.get('model') != MODEL or 'error' in data or record['cost'] > reserve
        except Exception as exc:
            record['error_type'] = type(exc).__name__
            record['fatal'] = True
        record['elapsed_seconds'] = time.monotonic() - started
        record['completed_utc'] = datetime.now(timezone.utc).isoformat()
        dump(out / (stem + '.json'), record)
        with lock:
            state['reserved'] -= reserve
            state['spent'] += record['cost']
            state['completed'] += 1
            state['stop'] |= record['fatal']
            if state['completed'] % 50 == 0 or record['fatal'] or not record['valid']:
                print(f"{state['completed']}/{len(schedule)} valid={record['valid']} fatal={record['fatal']} spent=${state['spent']:.4f}", flush=True)

    with ThreadPoolExecutor(max_workers=8) as pool:
        list(pool.map(worker, pending))
    dump(out / 'execution_summary.json', state)
    print(json.dumps(state), flush=True)


def analyze():
    from itertools import combinations
    from scripts.run_backtest import load_all_prices, load_universe
    from src.backtesting import engine
    from src.optimization.covariance import rolling_covariance
    from src.optimization.black_litterman import compute_prior
    from scripts.v2.analyze_informatica_text_ablation import allocate as allocate_neutral, weight_contrast, view_contrast
    from scripts.v2.analyze_informatica_portfolio_masking import allocate as allocate_masking, compare_weights
    manifest = json.loads((PREP / 'manifest.json').read_text())
    cases = manifest['cases']
    universe = load_universe(str(ROOT / 'config/universe.yaml'))
    prices = load_all_prices(ROOT / 'data/raw', universe['core'] + universe['holdout'])
    views = engine.load_views_summary(VIEWS / 'views_summary.csv')
    result = {'cases': len(cases), 'missing': manifest['missing'], 'model': MODEL}
    records = {}
    for exp in ARMS:
        run_dir = BASE / f'{exp}{SUFFIX}'
        rec, ids, cost, invalid = {}, [], 0., []
        for p in sorted(run_dir.glob('[0-9][0-9][0-9][0-9]_*.json')):
            r = json.loads(p.read_text())
            j = r['job']
            key = (j['case_id'], j['condition'], j['repeat'])
            assert key not in rec
            if not r['valid'] or r['fatal']:
                invalid.append(p.name)
                continue
            rec[key] = r['parsed']
            ids.append(r['response']['id'])
            cost += r['cost']
        expected = len(cases) * len(ARMS[exp]) * 3
        assert not invalid and len(rec) == expected == len(set(ids)), (exp, len(rec), expected, invalid[:5])
        records[exp] = rec
        result[exp] = {'complete_calls': len(rec), 'cost_usd': cost,
                       'confidence': {a: dict(Counter(rec[c['case_id'], a, r]['confidence'] for c in cases for r in range(1, 4))) for a in ARMS[exp]}}
    # Views: ablation contrasts (bps), all cases and per slice.
    rec = records['ablation']
    contrasts = [('real_text', 'no_text'), ('real_text', 'shuffled_text'), ('shuffled_text', 'no_text')]
    subsets = [('all', cases)] + [(d + '_' + g, [c for c in cases if c['date'] == d and c['group'] == g]) for d in DATES for g in ['core', 'holdout']]
    result['ablation']['view_contrasts'] = []
    for label, subset in subsets:
        arm = {a: np.array([[rec[c['case_id'], a, r]['view_bps'] for r in range(1, 4)] for c in subset]) for a in ARMS['ablation']}
        for a, b in contrasts:
            result['ablation']['view_contrasts'].append({'slice': label, 'a': a, 'b': b, **view_contrast(arm[a], arm[b])})
    mrec = records['masking']
    arm = {a: np.array([[mrec[c['case_id'], a, r]['view_bps'] for r in range(1, 4)] for c in cases]) for a in ARMS['masking']}
    result['masking']['view_contrast'] = view_contrast(arm['original'], arm['anonymized'])
    result['ablation']['weight_contrasts'], result['masking']['slices'] = [], []
    for date in DATES:
        for group in ['core', 'holdout']:
            subset = [c for c in cases if c['date'] == date and c['group'] == group]
            names = universe[group]
            cov = rolling_covariance(prices[names], pd.Timestamp(date), lookback=252)
            prior = compute_prior(cov, np.ones(50) / 50, 2.5)
            historical = {c['case_id']: json.loads((ROOT / c['source_view']).read_text())['view'] for c in subset}
            baseline, _ = allocate_masking(subset, historical, names, cov, prior)
            expected = engine._compute_strategy_weights(strategy='bl_llm_tilt_pos', prices=prices[names], views_df=views, tickers=names,
                                                        ticker_to_idx={t: i for i, t in enumerate(names)}, rebal_date=pd.Timestamp(date), n=50,
                                                        delta=2.5, tau=.05, risk_aversion=2.5, max_weight=.1, lookback=252, max_staleness_days=120)
            assert float(np.max(np.abs(baseline - expected))) < 1e-10, (date, group)
            for mode in ['end_to_end', 'all_support']:
                w = {a: np.stack([allocate_neutral(subset, {c['case_id']: rec[c['case_id'], a, r] for c in subset}, names, cov, prior, mode == 'all_support')[0] for r in range(1, 4)]) for a in ARMS['ablation']}
                for a, b in contrasts:
                    result['ablation']['weight_contrasts'].append({'date': date, 'group': group, 'mode': mode, 'a': a, 'b': b, **weight_contrast(w[a], w[b])})
            w = {a: np.stack([allocate_masking(subset, {c['case_id']: mrec[c['case_id'], a, r] for c in subset}, names, cov, prior)[0] for r in range(1, 4)]) for a in ARMS['masking']}
            result['masking']['slices'].append({'date': date, 'group': group, 'mode': 'end_to_end', **compare_weights(w['original'], w['anonymized'])})
    dump(BASE / ANALYSIS, result)
    print(json.dumps({k: (v if not isinstance(v, dict) else {kk: vv for kk, vv in v.items() if kk in ('complete_calls', 'cost_usd', 'confidence')}) for k, v in result.items()}, indent=2), flush=True)


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('command', choices=['prepare', 'run', 'analyze'])
    ap.add_argument('--experiment', choices=list(ARMS))
    ap.add_argument('--execute', action='store_true')
    ap.add_argument('--limit', type=int, default=0)
    ap.add_argument('--extra-dates', action='store_true', help='use the additional dates (separate folders)')
    a = ap.parse_args()
    if a.extra_dates:
        DATES[:] = EXTRA_DATES
        PREP = BASE / 'llm_inputs_extra_dates_v1'
        SUFFIX = '_gemini25flash_extra_dates_v1'
        ANALYSIS = 'llm_experiments_extra_dates_analysis.json'
    if a.command == 'prepare':
        prepare()
    elif a.command == 'run':
        run(a.experiment, a.execute, a.limit)
    else:
        analyze()
