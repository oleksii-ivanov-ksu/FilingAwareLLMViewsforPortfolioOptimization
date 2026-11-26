"""Minimal MO diagnostic repair. Frozen requests, resumable, no automatic retries."""
from pathlib import Path
import argparse
import hashlib
import importlib.util
import json
import os
import sys
import urllib.request
from datetime import datetime, timezone

import tiktoken
import yaml

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from scripts.v2.run_informatica_pilot import valid_response

BASE = ROOT / 'data/v2/analysis/informatica_revision/complete200_repair_v1'
CAP = .20


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path, obj):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2) + '\n')


def run(stage, execute):
    if stage == 'extraction':
        jobs = [{'name': 'extraction', 'request': 'extraction_request.json'}]
    else:
        assert json.loads((BASE / 'extraction_review.json').read_text())['passed']
        jobs = json.loads((BASE / 'repair_jobs.json').read_text())
        assert len(jobs) == 18
    out = BASE / 'responses'
    out.mkdir(exist_ok=True)
    inventory = {j['request']: sha(BASE / j['request']) for j in jobs}
    freeze = {'stage': stage, 'requests': inventory, 'combined_cap_usd': CAP,
              'model': 'x-ai/grok-4.3', 'automatic_retries': 0,
              'authorization': '2026-11-23 user: Окей выполняй необходимые доработки; minimal single-report repair, not full rerun',
              'runner_sha256': sha(Path(__file__))}
    freeze_path = BASE / (stage + '_freeze.json')
    if freeze_path.exists():
        assert json.loads(freeze_path.read_text()) == freeze
    else:
        write(freeze_path, freeze)
    if not execute:
        print(json.dumps({'stage': stage, 'requests': len(jobs), 'cap_usd': CAP}), flush=True)
        return
    # Verify model and prices before sending research content.
    with urllib.request.urlopen('https://openrouter.ai/api/v1/models', timeout=45) as response:
        catalog = json.load(response)
    model = next(m for m in catalog['data'] if m['id'] == freeze['model'])
    pin, pout = float(model['pricing']['prompt']), float(model['pricing']['completion'])
    assert pin <= .00000125 and pout <= .0000025
    write(BASE / (stage + '_model_catalog.json'), model)
    cfg = yaml.safe_load((ROOT / 'config/config.yaml').read_text())
    key = os.environ.get('OPENROUTER_API_KEY') or cfg['openai']['api_key']
    enc = tiktoken.get_encoding('o200k_base')
    spent = 0.
    for path in out.glob('*.json'):
        record = json.loads(path.read_text())
        assert record['valid'] and not record['fatal'], 'Prior failure requires audit'
        spent += record['cost']
    for job in jobs:
        path = out / (job['name'] + '.json')
        if path.exists():
            continue
        marker = out / (job['name'] + '.started')
        assert not marker.exists(), 'Ambiguous previous request: audit before retry'
        request_path = BASE / job['request']
        assert sha(request_path) == inventory[job['request']]
        payload = json.loads(request_path.read_text())
        reserve = (sum(len(enc.encode(m['content'])) for m in payload['messages']) + 1000) * pin + payload['max_tokens'] * pout
        assert spent + reserve <= CAP, 'Combined repair budget would be exceeded'
        marker.write_text(datetime.now(timezone.utc).isoformat())
        record = {'job': job, 'request_sha256': inventory[job['request']],
                  'reserved_max_cost': reserve, 'valid': False, 'fatal': True, 'cost': 0.}
        try:
            req = urllib.request.Request('https://openrouter.ai/api/v1/chat/completions',
                data=json.dumps(payload).encode(),
                headers={'Authorization': 'Bearer ' + key, 'Content-Type': 'application/json'})
            with urllib.request.urlopen(req, timeout=180) as response:
                data = json.load(response)
            record['response'] = data
            cost = data.get('usage', {}).get('cost')
            record['cost'] = float(cost or 0)
            if stage == 'extraction':
                spec = importlib.util.spec_from_file_location('repair_v1_schema', BASE / 'source_snapshot/schemas_v1.py')
                module = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(module)
                parsed = module.ExtractedFacts.model_validate_json(data['choices'][0]['message']['content']).model_dump(mode='json')
                assert data['choices'][0]['finish_reason'] == 'stop'
                assert parsed['ticker'] == 'MO' and parsed['filing_date'] == '2025-07-30' and parsed['filing_type'] == '10-Q'
            else:
                parsed = valid_response(data)
            record['parsed'] = parsed
            record['valid'] = parsed is not None
            record['fatal'] = cost is None or data.get('model') != freeze['model'] or record['cost'] > reserve or not record['valid']
        except Exception as exc:
            record['error_type'] = type(exc).__name__
        record['completed_utc'] = datetime.now(timezone.utc).isoformat()
        write(path, record)
        spent += record['cost']
        print(json.dumps({'job': job['name'], 'valid': record['valid'], 'fatal': record['fatal'], 'total_cost_usd': spent}), flush=True)
        if record['fatal']:
            raise SystemExit('Stopped: inspect saved response; no automatic retry')
    write(BASE / (stage + '_execution_summary.json'), {'complete': True, 'jobs': len(jobs), 'combined_cost_usd': spent})


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('stage', choices=['extraction', 'reasoning'])
    parser.add_argument('--execute', action='store_true')
    args = parser.parse_args()
    run(args.stage, args.execute)
