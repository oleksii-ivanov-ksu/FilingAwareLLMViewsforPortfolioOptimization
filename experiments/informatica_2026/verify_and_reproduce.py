"""Offline verification; copied to the archive root by the package builder."""
from pathlib import Path
import hashlib
import json
import shutil
import subprocess
import sys
import tempfile
import numpy as np


def compare(a, b):
    if isinstance(a,dict):
        assert a.keys() == b.keys()
        for k in a: compare(a[k],b[k])
    elif isinstance(a,list):
        assert len(a) == len(b)
        for x,y in zip(a,b): compare(x,y)
    elif isinstance(a,(int,float)) and not isinstance(a,bool):
        assert np.isclose(a,b,rtol=1e-10,atol=1e-12), (a,b)
    else:
        assert a == b, (a,b)


def main():
    base=Path(__file__).resolve().parent
    for name,digest in json.loads((base/'SHA256.json').read_text()).items():
        assert hashlib.sha256((base/name).read_bytes()).hexdigest() == digest, name
    rev=Path('data/v2/analysis/informatica_revision')
    with tempfile.TemporaryDirectory(prefix='informatica_verify_') as tmp:
        work=Path(tmp)/'replication'
        shutil.copytree(base,work)
        shutil.rmtree(work/rev/'financial_reanalysis_v1')
        for script in ['reanalyze_informatica_returns','analyze_informatica_pilot','audit_informatica_sensitivity','informatica_figures_and_tables','reproduce_informatica_extensions','reproduce_informatica_text_ablation']:
            subprocess.run([sys.executable,str(work/'scripts/v2'/f'{script}.py')],cwd=work,check=True,stdout=subprocess.DEVNULL)
            print(f'Completed {script}',flush=True)
        for name in ['financial_reanalysis_v1/results.json','grok43_replication_v1/analysis.json','sensitivity_audit/validation.json']:
            compare(json.loads((base/rev/name).read_text()),json.loads((work/rev/name).read_text()))
        for p in (base/'paper/informatica/tables').glob('*.md'):
            assert p.read_bytes()==(work/p.relative_to(base)).read_bytes(),p.name
    print('PASS: all hashes, financial and pilot statistics, sensitivity audit and paper tables.',flush=True)


if __name__ == '__main__':
    main()
