Informatica editorial V2: offline signal and risk extension, 2026-11-16

Reproduce from saved derived outputs (no API keys, no LLM calls):
  python -m venv .venv
  .venv/bin/pip install -r requirements.txt
  .venv/bin/python verify.py

The verifier checks every SHA-256, all portfolio metrics, defined quarterly
rank ICs, beta/prior identity and all 448 factor regressions. SUPPLEMENT_S11.md
specifies the protocol, definitions, limitations and table interpretations.

results/ holds per-date view/outcome panels, date-level diagnostics, portfolio
returns/targets/turnover, rolling Sharpe, subperiods and regression outputs.
The original view values and realized outcomes are derived research records;
no raw SEC text, private prompts, API keys or raw FMP price files are included.
The outcome panel supports statistical reproduction, not independent recovery
of licensed price history. analysis_source.py records the full calculation;
its raw-input mode requires the original project checkout and source files.

factors.csv is the through-2025 subset of the 2026-09-07 cached Kenneth French
factor snapshot (daily FF5 and momentum). Source:
https://mba.tuck.dartmouth.edu/pages/faculty/ken.french/data_library.html
The internal model label FF3+Mom denotes a four-factor regression using SMB
and HML from the FF5 file; it is not a separate canonical FF3-file replication.

Protocol assertions and independent checks are retained. The tests remain
post hoc and do not remedy model-training leakage or survivor selection.
