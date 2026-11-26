# Cover letter draft — Informatica V2

Dear Editors,

Please consider “Evaluating LLM-Based Integration of Corporate Filings into Black–Litterman Portfolio Construction” by Oleksii Ivanov and Vitaliy Kobets for publication in Informatica.

The article evaluates a two-stage filing-to-view pipeline and its portfolio allocation mechanism on two fixed groups of 50 companies. BL-Filing+ has higher historical CAGR than equal weighting (15.67%/13.24% versus 12.19%/10.66%) with greater volatility and drawdown. The revised evaluation combines paired inference, direct quarterly signal tests, matched allocation controls, factor attribution and proportional-cost sensitivity. A repeated content ablation establishes that filing summaries affect views and weights. The financial controls clarify which aspects of the historical outcome can also arise without numerical LLM views.

A previous version was rejected by Computational Economics. The revision addresses that assessment through explicit temporal and universe-selection limitations, corrected metric reporting and additional controls; it does not claim to have removed historical model-information leakage. Code, derived outputs, protocols and offline verifiers are available together in https://github.com/oleksii-ivanov-ksu/FilingAwareLLMViewsforPortfolioOptimization.

We disclose the companion manuscript “Comparing LLM Pipeline Architectures for Portfolio Views from Financial Filings,” which uses shared project data to compare one-stage and two-stage architectures, quote verification and top/bottom selection. The present article evaluates historical v1 Black–Litterman configurations and second-stage input interventions. The shared data are disclosed in Section 6, and the companion’s results are not treated as an independent replication. Its current editorial status should be confirmed by the authors and the manuscript supplied to the editor with the submission.

Grok generated the experimental model outputs. Codex assisted with auditing, statistical reanalysis, manuscript preparation and formatting; this use is disclosed in the article.

Sincerely,

Vitaliy Kobets, corresponding author
Kherson State University, 27 Universitetska St., Kherson 73003, Ukraine
vkobets@kse.org.ua

Author checklist before sending: confirm approval by both authors, exclusive submission, funding and conflicts declarations, and the companion manuscript’s current editorial status. This draft has not been sent and does not assert these confirmations on the authors’ behalf.
