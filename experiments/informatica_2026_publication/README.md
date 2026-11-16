# Informatica V2 publication audit

This package is the authoritative realized-RF update to the main article. Earlier packages preserve fixed-2% results as dated audit records. All packages live in this GitHub repository; no Drive archive or Zenodo deposit is needed.

From the repository root:

```bash
python3 -m venv .venv-audit
source .venv-audit/bin/activate
python -m pip install -r experiments/informatica_2026_publication/requirements.txt
python experiments/informatica_2026_publication/verify.py
```

The verifier runs offline and recomputes all primary metrics, cost scenarios, DSR scenarios and 10,000-draw bootstrap comparisons. It reads only files in this package and writes no model outputs. No API key or paid request is required. Allow approximately one minute. SHA256.json covers input/output artifacts; independent_checks.json records the additional private-price replay check performed before release. Raw vendor prices are not redistributed.

Read SUPPLEMENT_S12.md for assumptions and limitations. `analysis_source.py` is the original workspace audit script, retained for provenance; use `verify.py` for standalone reproduction. `results/comparisons.csv` contains all 5/21/63-day blocks; `metrics.csv` reconciles actual RF and constant 2%; `costs.csv` includes all six diagnostic arms. Candidate returns are derived portfolio series, not raw vendor data.
