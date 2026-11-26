"""Prepare and analyze a minimal, provenance-preserving 200-case augmentation."""
from pathlib import Path
from collections import Counter
import argparse
import csv
import hashlib
import json
import random
import re
import sys
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from scripts.v2.run_informatica_complete200_repair import BASE, write, sha
from scripts.v2.prepare_informatica_portfolio_masking import identity_mask
from scripts.v2.prepare_informatica_text_ablation import split_prompt
from scripts.v2.run_informatica_text_ablation import CONFIG
from scripts.v2 import analyze_informatica_text_ablation as text_analysis
from scripts.v2 import analyze_informatica_portfolio_masking as masking_analysis
from src.reasoning.input_builder import InputBuilder
from src.reasoning.prompts import REASONER_SYSTEM_PROMPT, format_user_prompt
from scripts.run_backtest import load_all_prices, load_universe
from src.optimization.covariance import rolling_covariance
from src.optimization.black_litterman import compute_prior

PARENT = BASE.parent
OLD_TEXT = PARENT / 'text_ablation_preparation_v1'
OLD_MASK = PARENT / 'portfolio_masking_preparation_v1'


def prepare():
    assert not (BASE / 'repair_jobs.json').exists(), 'Prepared inputs are immutable'
    assert json.loads((BASE / 'extraction_review.json').read_text())['passed']
    for parent in [OLD_TEXT, OLD_MASK]:
        for name, digest in json.loads((parent / 'checksums.json').read_text()).items():
            assert sha(parent / name) == digest, name
    facts = json.loads((BASE / 'responses/extraction.json').read_text())['parsed']
    write(BASE / 'extracted/MO/10-Q_2025-07-30.json', facts)
    builder = InputBuilder(ROOT / 'data/extracted', ROOT / 'data/raw', ROOT / 'data/constituents.csv')
    old_facts = dict(builder._load_extracted_facts('MO'))
    old_facts['10-Q_2025-07-30'] = facts
    builder._extracted_cache['MO'] = old_facts
    inp = builder.build_input_for_filing('MO', facts)
    assert inp is not None and inp.latest_10q_date == '2025-07-30'
    assert str(inp.view_date) == '2025-07-31' and inp.earnings_surprise is not None
    # Fiscal-period narrative is retained verbatim from extraction; no tuned edits.
    messages = [{'role': 'system', 'content': REASONER_SYSTEM_PROMPT},
                {'role': 'user', 'content': format_user_prompt(inp)}]
    old_system = json.loads((OLD_MASK / 'cases/W001/original_messages.json').read_text())[0]
    assert messages[0] == old_system
    company = next(r['Security'] for r in csv.DictReader((ROOT / 'data/constituents.csv').open()) if r['Symbol'] == 'MO')
    masked, changes = identity_mask(messages[1]['content'], 'MO', company)
    assert changes
    anonymous = [messages[0], {'role': 'user', 'content': masked}]
    write(BASE / 'W200_reconstructed_input.json', inp.model_dump(mode='json'))
    write(BASE / 'W200_original_messages.json', messages)
    write(BASE / 'W200_anonymized_messages.json', anonymous)
    write(BASE / 'W200_identity_changes.json', changes)
    cases = json.loads((OLD_TEXT / 'manifest.json').read_text())['cases']
    recipient = min((c for c in cases if c['date'] == '2025-09-30' and c['group'] == 'holdout'), key=lambda c: c['case_id'])
    former_donor = recipient['donor_case_id']
    mo = {'case_id': 'W200', 'ticker': 'MO', 'date': '2025-09-30', 'group': 'holdout',
          'view_date': str(inp.view_date), 'fiscal_period': inp.fiscal_period,
          'sentiment': facts['sentiment'], 'source_view': None,
          'source_fact': str((BASE / 'extracted/MO/10-Q_2025-07-30.json').relative_to(ROOT)),
          'donor_case_id': former_donor, 'repair_extraction_model': 'x-ai/grok-4.3'}
    recipient['donor_case_id'] = 'W200'
    cases.append(mo)
    for date in ['2015-09-30', '2025-09-30']:
        for group in ['core', 'holdout']:
            subset = [c for c in cases if c['date'] == date and c['group'] == group]
            assert len(subset) == 50
            assert {c['case_id'] for c in subset} == {c['donor_case_id'] for c in subset}
            assert all(c['case_id'] != c['donor_case_id'] for c in subset)
    jobs = []
    for condition, prompt in [('original', messages), ('anonymized', anonymous)]:
        for repeat in range(1, 4):
            name = f'masking_W200_{condition}_{repeat}'
            request = 'requests/' + name + '.json'
            write(BASE / request, dict(CONFIG, messages=prompt))
            jobs.append({'name': name, 'request': request, 'experiment': 'masking', 'case_id': 'W200', 'condition': condition, 'repeat': repeat})
    mo_text = split_prompt(messages)[1]
    for c in [mo, recipient]:
        cid = c['case_id']
        original = messages if cid == 'W200' else json.loads((OLD_MASK / 'cases' / cid / 'original_messages.json').read_text())
        prefix, own, financial = split_prompt(original)
        prefix = f"Generate an investment view for {c['ticker']} as of {c['date']}.\n" + prefix.split('\n', 1)[1]
        donor_text = mo_text if c['donor_case_id'] == 'W200' else split_prompt(json.loads((OLD_MASK / 'cases' / c['donor_case_id'] / 'original_messages.json').read_text()))[1]
        blocks = {'real_text': own, 'no_text': '', 'shuffled_text': donor_text} if cid == 'W200' else {'shuffled_text': donor_text}
        for condition, block in blocks.items():
            assert all(d <= c['date'] for d in re.findall(r'filed (\d{4}-\d{2}-\d{2})', block))
            prompt = [original[0], {'role': 'user', 'content': prefix + block + financial}]
            if cid != 'W200':
                previous = json.loads((OLD_TEXT / 'cases' / cid / 'shuffled_text_1_messages.json').read_text())
                assert split_prompt(previous)[0] == prefix and split_prompt(previous)[2] == financial
            for repeat in range(1, 4):
                name = f'content_{cid}_{condition}_{repeat}'
                request = 'requests/' + name + '.json'
                write(BASE / request, dict(CONFIG, messages=prompt))
                jobs.append({'name': name, 'request': request, 'experiment': 'content', 'case_id': cid, 'condition': condition, 'repeat': repeat})
    random.Random(20261123).shuffle(jobs)
    assert len(jobs) == 18
    write(BASE / 'manifest.json', {'dates': ['2015-09-30', '2025-09-30'], 'cases': cases,
          'changed_recipient': recipient['case_id'], 'former_donor': former_donor,
          'selection': 'Minimal later augmentation; original 199 cases retained, no outcome reselection',
          'masking_frozen_support': 'Historical v1 support; MO remains excluded'})
    write(BASE / 'repair_jobs.json', jobs)
    write(BASE / 'prepared_hashes.json', {str(p.relative_to(BASE)): sha(p) for p in sorted((BASE / 'requests').glob('*.json'))})
    print(json.dumps({'cases': len(cases), 'jobs': len(jobs), 'changed_recipient': recipient['case_id'], 'former_donor': former_donor}), flush=True)


def load_records(experiment):
    directory = PARENT / ('text_ablation_grok43_v1' if experiment == 'content' else 'portfolio_masking_grok43_v1')
    records, provenance = {}, {}
    for p in sorted(directory.glob('[0-9][0-9][0-9][0-9]_*.json')):
        r = json.loads(p.read_text()); j = r['job']
        key = (j['case_id'], j['condition'], j['repeat'])
        assert key not in records and r['valid'] and not r['fatal']
        records[key] = r
        provenance[key] = {'path': str(p.relative_to(ROOT)), 'sha256': sha(p), 'reused': True}
    replaced = []
    for j in json.loads((BASE / 'repair_jobs.json').read_text()):
        if j['experiment'] != experiment:
            continue
        p = BASE / 'responses' / (j['name'] + '.json')
        r = json.loads(p.read_text())
        assert r['valid'] and not r['fatal']
        request = BASE / j['request']
        assert r['request_sha256'] == sha(request)
        key = (j['case_id'], j['condition'], j['repeat'])
        if key in records:
            replaced.append(provenance[key])
        records[key] = r
        provenance[key] = {'path': str(p.relative_to(ROOT)), 'sha256': sha(p), 'reused': False}
    expected = 1800 if experiment == 'content' else 1200
    assert len(records) == expected
    assert len({r['response']['id'] for r in records.values()}) == expected
    assert len(replaced) == (3 if experiment == 'content' else 0)
    write(BASE / (experiment + '_response_inventory.json'),
          {'active': [{'key': list(k), **v} for k, v in provenance.items()], 'superseded': replaced})
    return records


def analyze():
    manifest = json.loads((BASE / 'manifest.json').read_text()); cases = manifest['cases']
    universe = load_universe(str(ROOT / 'config/universe.yaml'))
    prices = load_all_prices(ROOT / 'data/raw', universe['core'] + universe['holdout'])
    text_records, mask_records = load_records('content'), load_records('masking')
    views = []
    subsets = [('all', cases)] + [(d + '_' + g, [c for c in cases if c['date'] == d and c['group'] == g]) for d in manifest['dates'] for g in ['core', 'holdout']]
    for label, subset in subsets:
        arms = {a: np.array([[text_records[c['case_id'], a, r]['parsed']['view_bps'] for r in range(1, 4)] for c in subset]) for a in text_analysis.ARMS}
        for a, b in text_analysis.CONTRASTS:
            views.append({'slice': label, 'a': a, 'b': b, **text_analysis.view_contrast(arms[a], arms[b])})
    contrasts, summaries, targets, mask_rows, mask_targets = [], [], {}, [], {}
    for date in manifest['dates']:
        for group in ['core', 'holdout']:
            subset = [c for c in cases if c['date'] == date and c['group'] == group]
            names = universe[group]
            cov = rolling_covariance(prices[names], pd.Timestamp(date), lookback=252)
            prior = compute_prior(cov, np.ones(50) / 50, 2.5)
            for mode in ['end_to_end', 'all_support']:
                arms = {}
                for condition in text_analysis.ARMS:
                    arrays, counts = [], []
                    for repeat in range(1, 4):
                        outputs = {c['case_id']: text_records[c['case_id'], condition, repeat]['parsed'] for c in subset}
                        w, selected = text_analysis.allocate(subset, outputs, names, cov, prior, mode == 'all_support')
                        assert np.isfinite(w).all() and np.min(w) >= 0
                        np.testing.assert_allclose(w.sum(), 1, atol=1e-12)
                        arrays.append(w); counts.append(len(selected))
                    arms[condition] = np.stack(arrays)
                    summaries.append({'date': date, 'group': group, 'mode': mode, 'condition': condition, 'accepted_counts': counts,
                                      'hhi': (arms[condition] ** 2).sum(1).tolist(), 'max_weights': arms[condition].max(1).tolist()})
                for a, b in text_analysis.CONTRASTS:
                    contrasts.append({'date': date, 'group': group, 'mode': mode, 'a': a, 'b': b, **text_analysis.weight_contrast(arms[a], arms[b])})
                targets[date + '_' + group + '_' + mode] = {'tickers': names, 'weights': {a: v.tolist() for a, v in arms.items()}}
            for mode in ['end_to_end', 'frozen_support']:
                # No historical MO view exists. Preserve the historical support.
                allocation_cases = subset if mode == 'end_to_end' else [c for c in subset if c['source_view'] is not None]
                arms, sets, counts = {}, {}, {}
                for condition in ['original', 'anonymized']:
                    arrays, accepted_sets = [], []
                    counts[condition] = Counter()
                    for repeat in range(1, 4):
                        outputs = {c['case_id']: mask_records[c['case_id'], condition, repeat]['parsed'] for c in subset}
                        w, selected = masking_analysis.allocate(allocation_cases, outputs, names, cov, prior, mode == 'frozen_support')
                        assert np.isfinite(w).all() and np.min(w) >= 0
                        np.testing.assert_allclose(w.sum(), 1, atol=1e-12)
                        arrays.append(w); accepted_sets.append(set(selected))
                        counts[condition].update(o['confidence'] for o in outputs.values())
                    arms[condition] = np.stack(arrays); sets[condition] = accepted_sets
                stats = masking_analysis.compare_weights(arms['original'], arms['anonymized'])
                stats.update(accepted_counts_original=[len(s) for s in sets['original']], accepted_counts_masked=[len(s) for s in sets['anonymized']],
                             mean_cross_selected_symmetric_difference=float(np.mean([len(a ^ b) for a in sets['original'] for b in sets['anonymized']])),
                             confidence_counts={k: dict(v) for k, v in counts.items()})
                mask_rows.append({'date': date, 'group': group, 'mode': mode, **stats})
                mask_targets[date + '_' + group + '_' + mode] = {k: v.tolist() for k, v in arms.items()}
    # The unaffected slices must reproduce exactly before augmented results are used.
    old_text = json.loads((PARENT / 'text_ablation_grok43_v1/targets.json').read_text())
    old_mask = json.loads((PARENT / 'portfolio_masking_grok43_v1/targets.json').read_text())
    errors = []
    for key, value in targets.items():
        if key.startswith('2025-09-30_holdout'):
            continue
        for condition, w in value['weights'].items():
            errors.append(float(np.max(np.abs(np.array(w) - old_text[key]['weights'][condition]))))
    for key, value in mask_targets.items():
        if key == '2025-09-30_holdout_end_to_end':
            continue
        for condition, w in value.items():
            errors.append(float(np.max(np.abs(np.array(w) - old_mask[key][condition]))))
    assert max(errors) < 1e-12
    confidence = {a: dict(Counter(r['parsed']['confidence'] for k, r in text_records.items() if k[1] == a)) for a in text_analysis.ARMS}
    text_result = {'cases': 200, 'complete_calls': 1800, 'new_calls': 12, 'reused_calls': 1788, 'superseded_calls': 3,
                   'view_contrasts': views, 'weight_contrasts': contrasts, 'weight_summaries': summaries, 'confidence': confidence}
    transitions = Counter()
    for c in cases:
        for i in range(1, 4):
            for j in range(1, 4):
                a = mask_records[c['case_id'], 'original', i]['parsed']['confidence']
                b = mask_records[c['case_id'], 'anonymized', j]['parsed']['confidence']
                transitions[a + ' -> ' + b] += 1
    mask_result = {'cases': 200, 'complete_calls': 1200, 'new_calls': 6, 'reused_calls': 1194,
                   'slices': mask_rows, 'confidence_transitions_all_cross_pairs': dict(transitions)}
    for name, obj in [('content_analysis.json', text_result), ('content_targets.json', targets), ('masking_analysis.json', mask_result), ('masking_targets.json', mask_targets)]:
        write(BASE / name, obj)
    records = [json.loads(p.read_text()) for p in (BASE / 'responses').glob('*.json')]
    assert len(records) == 19 and all(r['valid'] and not r['fatal'] for r in records)
    cost = sum(r['cost'] for r in records)
    assert cost <= .20
    validation = {'status': 'PASS', 'cases': 200, 'slices': 4, 'cases_per_slice': 50,
                  'new_paid_calls': 19, 'new_reasoning_calls': 18, 'new_extraction_calls': 1,
                  'repair_cost_usd': cost, 'active_diagnostic_responses': 3000,
                  'archived_diagnostic_responses_including_pilot_and_superseded': 3303,
                  'unaffected_targets_max_error': max(errors), 'historical_backtest_changed': False,
                  'augmentation_not_fresh_200_case_run': True}
    write(BASE / 'validation.json', validation)
    print(json.dumps(validation, indent=2), flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('action', choices=['prepare', 'analyze'])
    args = parser.parse_args()
    prepare() if args.action == 'prepare' else analyze()
