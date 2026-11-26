# Complete 200-case filing diagnostic

This package adds the missing Altria (MO) input to the existing experiments. It contains 200 company/date inputs, four slices of 50 companies, 1,800 active content-ablation responses and 1,200 masking responses. It is a later augmentation of the original 199-case runs, not a fresh 200-case run.

## Reproduce without API calls

From the repository root:

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -r experiments/informatica_2026_complete200/requirements.txt
python experiments/informatica_2026_complete200/verify.py
```

The verifier checks every packaged SHA-256, coverage, unique generations, response counts, confidence shares, view contrasts and portfolio distances. It independently reconstructs all content/masking weight vectors using the precision-space Black–Litterman formula, starting from saved covariance matrices and priors. Raw price history and API keys are not needed. Covariances are derived inputs; the verifier does not independently certify their historical data vintage.

## Results

| Comparison | Original 199 cases | Augmented 200 cases |
|---|---:|---:|
| Mean absolute view change, own vs no summaries (bps) | 26.88 | 27.10 |
| Mean absolute view change, own vs shuffled summaries (bps) | 36.88 | 37.09 |
| Cross-minus-within view distance, own vs no summaries (bps) | 16.18 | 16.43 |
| Cross-minus-within view distance, own vs shuffled summaries (bps) | 23.98 | 24.19 |
| 2025 additional-group weight distance, own vs no summaries (%) | 13.83 | 13.77 |
| 2025 additional-group weight distance, own vs shuffled summaries (%) | 14.57 | 14.38 |

The other three slices reproduce exactly. End-to-end masking weight distances are unchanged at the reported precision. Filing summaries still change views and weights beyond the observed repeat variability in all four slices. This diagnostic does not estimate subsequent portfolio returns; the historical backtest and IC/factor analyses remain unchanged.

## Repair and accounting

The original July 30, 2025 MO download contained an SEC XBRL Viewer shell. The actual filing is included as `MO_10-Q_2025-07-30.html`. FMP metadata and the SEC accession identify the same report, period ended June 30, 2025. Source: https://www.sec.gov/Archives/edgar/data/764180/000076418025000111/mo-20250630.htm

One extraction used the published v1 prompt/schema and Grok 4.3 because Grok 4.1 Fast was unavailable. `source_provenance.json` is the initial preparation snapshot; completion is recorded in `validation.json`, the response files and execution freezes. `extraction_review.json` records the source checks. This is not a restored Grok 4.1 Fast response.

Only 18 reasoning calls were made: nine content conditions/repeats for W200 (MO), six masking responses for W200, and three replacement shuffled responses for W151 (AEP). W151 is the lexicographically first case in the affected slice. Its former donor W177 now supplies W200; W200 supplies W151. No other donor assignment changed. All existing outputs for unchanged requests were retained. All three new repeats use the same donor. The historical fixed-support masking check still excludes MO because no eligible historical v1 view existed; the main end-to-end analysis includes all 200 inputs.

There are 3,000 active diagnostic responses: 2,982 reused and 18 new. Three displaced shuffled responses remain in the original package. Including the separate 300-response pilot, the archive contains 3,303 generated diagnostic responses. One new extraction is separate from that count. The 19-call repair cost $0.10999135; the hard cap was $0.20. Run dates, model IDs and generation IDs are retained, so the later additions can be identified.

## Files

- `content_records.json`, `masking_records.json`: all active parsed answers, generation IDs and costs.
- `manifest.json`: company/date cases, donor map, historical fixed support.
- `allocation_inputs.json`: four covariance matrices, priors and ticker order.
- `*_analysis.json`, `*_targets.json`: recomputed metrics and all portfolio weights.
- `requests/`, `responses/`, `extraction_request.json`: exact new requests and unmodified provider responses; no credentials.
- `source_snapshot/`: v1 extraction prompt/schema from the published commit.
- `source/`: project-side preparation/execution/analysis scripts. These require the original workspace; the standalone verifier above does not.
- `minimal_protocol.md`: protocol frozen before new diagnostic answers.
- `SHA256.json`: integrity inventory.

The original packages remain archived under `experiments/informatica_2026`, `experiments/informatica_2026_signal_risk` and `experiments/informatica_2026_publication`.
