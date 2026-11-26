# Gemini 2.5 Flash package (article data)

This package holds the data behind the article *Evaluating LLM-Based Integration of Corporate Filings into Black–Litterman Portfolio Construction*. Both pipeline stages run on `google/gemini-2.5-flash`: stage one extracts risks, management guidance and corporate events from a filing with a verbatim quote for every fact, stage two turns the extracted record and financial indicators into a numerical view. The other packages in `experiments/` document experiments with Grok 4.1 Fast and are kept as dated records.

## Reproduce without API calls

From the repository root:

```bash
python3 -m venv .venv-v5
source .venv-v5/bin/activate            # Windows: .venv-v5\Scripts\activate
python -m pip install -r experiments/informatica_2026_v5_gemini/requirements.txt
python experiments/informatica_2026_v5_gemini/verify.py
```

The verifier reads only files of this package. It needs no API key and no price history, and takes about a minute. It checks every SHA-256 and then recomputes the reported numbers; a number passes when the recomputed value rounds to the one printed in the article.

| Step | What is recomputed | From |
|---|---|---|
| 1 | integrity of all files | `SHA256.json` |
| 2 | Tables 4 and 5: CAGR, Sharpe ratio, maximum drawdown, volatility, the control portfolio, both permutation schemes (100 runs each), the relative view specification | daily returns in `portfolio/` |
| 3 | Sharpe-ratio differences with 95 % intervals (paired block bootstrap, 21-day blocks, 10,000 draws), the mean-return test and the Holm adjustment over eight comparisons | `portfolio/*_returns.csv` |
| 4 | turnover and CAGR at 5, 10 and 20 basis points of cost | `portfolio/*_controls_turnover.csv` |
| 5 | text removal, text replacement and name masking: mean view change, excess over repeat variability with intervals, Table 3 weight distances | `experiments/records.json`, `experiments/weights.json` |
| 6 | Table 1: recall, precision and F1 of eight models on the manually annotated set of 90 filings, with bootstrap intervals over filings; share of facts with a located quote | `extraction/`, `corpus/extracted_facts_gemini.zip` |
| 7 | information coefficient, alpha of the return difference, market loadings | `signal/`, `portfolio/` |

## Contents

**`portfolio/`** — daily returns of the six portfolio variants (`*_returns.csv`), of the control portfolio without model views and other rule-based controls (`*_controls_returns.csv`), of the relative view specification (`*_relative_returns.csv`) and of 200 permutation runs (`*_matched_returns.csv.gz`); rebalance weights of the controls (`*_controls_weights.npz`); charged turnover; the daily factor file from the Kenneth R. French Data Library (`factors.csv`). `saved/` keeps the statistics as originally computed.

**`experiments/`** — the text and name experiments on 499 company-date cases at five dates (30 September 2010, 2015, 2020, 2023 and 2025).

- `cases.json`, `design.json`: the cases and the dates of the two collection rounds.
- `records.json`: all 7,485 parsed answers (4,491 for text removal and replacement, 2,994 for name masking) with generation identifiers, token counts and cost.
- `weights.json`: portfolio weights for every condition and repeat, ten slices of 50 stocks.
- `inputs_*_dates.zip`: the prepared inputs for every case and condition.
- `raw_*_dates.zip`: the exact requests and unmodified provider responses. No credentials.

**`extraction/`** — the manually annotated set (`gold_standard/`, 90 filings, 850 events), the answers of the eight compared models on this set (`model_events.zip`) and the saved evaluation.

**`corpus/`** — stage-one output for 9,100 filings (`extracted_facts_gemini.zip`), stage-two views for 8,001 filings of 2006–2025 (`views_gemini.zip`) and their summary table (`views_summary.csv`). Each extraction file ends with a `grounding` block: how many facts were checked against the filing text and how many were found.

**`signal/`** — views with the return of the following quarter for every rebalance date and stock.

**`figures/`** — Figures 2 and 3 of the article.

**`source/`** — snapshot of the code that produced these files: the shared library (`src/`), the stage scripts and the analysis scripts (`scripts/v2/v5_gemini/`). Running them requires the full workspace with price history; the standalone verifier does not.

## Provenance

- Model identifier `google/gemini-2.5-flash`, accessed through OpenRouter; reasoning mode not set.
- Model comparison on the annotated set: 30–31 August 2026. Corpus extraction and views: 31 August – 1 September 2026. Text and name experiments: 25 November 2026.
- Temperature 0.1 at stage one and 0.3 at stage two.
- The company list with the split into two groups of 50 is in `config/universe.yaml` at the repository root.

## Not included

- Price history and analyst data from Financial Modeling Prep (licensed). Returns and weights computed from them are included, and `scripts/download_raw_data.py` downloads the inputs with your own key.
- Filing texts: they are public on SEC EDGAR, and `scripts/download_sec_filings.py` downloads them.
- API credentials.

## Limits of this package

The verifier confirms that the reported numbers follow from the saved files. It does not re-run the language model: repeated calls give slightly different answers, which is why every experimental condition was collected three times and why the saved answers, not new ones, define the reported results. Portfolio weights are included as computed; recomputing them from prices requires the licensed market data.
