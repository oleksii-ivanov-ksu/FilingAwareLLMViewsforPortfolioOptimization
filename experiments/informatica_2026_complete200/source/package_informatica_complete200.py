"""Build a small standalone offline reproduction package; no API calls."""
from pathlib import Path
import json
import shutil
import sys
import hashlib
import numpy as np
import pandas as pd
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from scripts.v2.augment_informatica_complete200 import BASE, load_records, write, load_universe, load_all_prices, rolling_covariance, compute_prior


def main():
    out = ROOT / 'paper/informatica/v2_evaluation/complete200_reproduction'
    out.mkdir(exist_ok=True)
    manifest = json.loads((BASE / 'manifest.json').read_text())
    for experiment in ['content', 'masking']:
        records = load_records(experiment)
        minimal = [{'case_id': k[0], 'condition': k[1], 'repeat': k[2], **r['parsed'],
                    'generation_id': r['response']['id'], 'cost': r['cost']} for k, r in sorted(records.items())]
        write(out / (experiment + '_records.json'), minimal)
    cases = manifest['cases']
    for c in cases:
        if c['source_view']:
            historical = json.loads((ROOT / c['source_view']).read_text())['view']
            c['historical_selected'] = historical['confidence'] == 'medium' and historical['view_bps'] > 0
        else:
            c['historical_selected'] = False
    write(out / 'manifest.json', manifest)
    universe = load_universe(str(ROOT / 'config/universe.yaml'))
    prices = load_all_prices(ROOT / 'data/raw', universe['core'] + universe['holdout'])
    allocation = {}
    for date in manifest['dates']:
        for group in ['core', 'holdout']:
            names = universe[group]
            cov = rolling_covariance(prices[names], pd.Timestamp(date), lookback=252)
            prior = compute_prior(cov, np.ones(50)/50, 2.5)
            allocation[date + '_' + group] = {'tickers': names, 'covariance': cov.tolist(), 'prior': prior.tolist()}
    write(out / 'allocation_inputs.json', allocation)
    for name in ['content_analysis.json', 'masking_analysis.json', 'content_targets.json', 'masking_targets.json', 'validation.json', 'extraction_review.json', 'source_provenance.json', 'minimal_protocol.md', 'extraction_freeze.json', 'reasoning_freeze.json', 'repair_jobs.json', 'extraction_request.json', 'W200_reconstructed_input.json', 'W200_identity_changes.json', 'MO_10-Q_2025-07-30.html']:
        shutil.copyfile(BASE / name, out / name)
    for folder in ['requests', 'responses', 'source_snapshot']:
        shutil.copytree(BASE / folder, out / folder, dirs_exist_ok=True, ignore=shutil.ignore_patterns('*.started', '__pycache__'))
    for script in ['run_informatica_complete200_repair.py', 'augment_informatica_complete200.py', 'package_informatica_complete200.py']:
        (out / 'source').mkdir(exist_ok=True)
        shutil.copyfile(ROOT / 'scripts/v2' / script, out / 'source' / script)
    shutil.copyfile(ROOT / 'scripts/v2/verify_informatica_complete200.py', out / 'verify.py')
    (out / 'requirements.txt').write_text('numpy>=1.24\n')
    files = {str(p.relative_to(out)): hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(out.rglob('*')) if p.is_file() and p.name != 'SHA256.json'}
    write(out / 'SHA256.json', files)
    print(out, flush=True)


if __name__ == '__main__':
    main()
