# Publication audit prose review

Academic-humanizer applied in two passes: (1) revise the scientific account against the computed audit, (2) remove repeated qualifiers and check protected numbers, citations and defined terms.

## Change log — substantive changes

- “Sharpe ratios are 0.635/0.547 versus 0.565/0.496” → “0.649/0.569 versus 0.581/0.522”. This is a disclosed change from constant 2% to realized daily RF, not an improvement in saved returns; all primary tables and intervals were recalculated.
- “Market betas are 1.035/1.035” → “1.0352/1.0354”. Increased precision distinguishes the independently fitted estimates.
- “The additional diagnostics ... are supplied separately ... not included in commit de10d6c” → all three packages are in the same GitHub repository. Publication must be verified before this statement is treated as delivered.
- Repeated “does not establish” sentences → concrete descriptions of IC, risk controls and interval width, with temporal validity and selection limitations retained in Section 6. No claim of forecasting value, equivalence or historical investability was added.
- Added conditional DSR scenarios, MDE and cost sensitivity from publication_audit_v1. DSR is explicitly distinguished from a test against EW and from identification of a filing signal.

No further meaning changes in the second stylistic pass. Author names, ORCIDs, affiliations, correspondence, historical CAGR, IC and ablation results were preserved. The unchanged Slovenian summary still describes the same scientific conclusions; final native-language author review remains appropriate.

## Citation needed

None. New literature metadata was checked against primary sources: ACL Anthology, arXiv, CFA Institute and the DSR author manuscript. Bibliography and in-text citations are numbered by first occurrence (1–21).


# Editorial follow-up — 16 November 2026

No new experiment, API request or statistical calculation was performed. Table additions use the existing publication-audit outputs.

## Authorized substantive changes

- Retained the primary historical return results. The abstract and Section 5.6 explicitly identify EW as the comparator for cost robustness.
- Shortened main-text DSR to one sentence retaining 0.987/0.984, the assumed 24 effective trials, its selection-adjusted zero-Sharpe benchmark and the S12 pointer. This is not a test against EW or proof of text value. Full assumptions and sensitivity results remain in S12.
- Expanded Table 6 with existing volatility-tilt and horizon-aligned Sharpe values. Labelled prior-only/beta equivalence and median-of-100 reassignment results.
- Added Table 8 with existing CAGR at 5/10/20 bp for BL-Filing+, EW, prior/beta and volatility tilts. The volatility tilt has higher CAGR in both groups at all three costs.
- Made the masking limitation explicit: four slices and three repeats do not demonstrate a stable effect beyond repeat variability; they do not establish zero effect. Kept content ablation separate and stated the Grok 4.3 / historical Grok 4.1 Fast mismatch.
- Explicitly stated that 1-, 5- and 21-day post-filing outcomes were not evaluated; quarterly IC does not answer that question.
- Added Glasserman–Lin (published 2024 version), Sarkar–Vafa (2024 working paper), Ledoit–Wolf (2008) and Frazzini–Pedersen (2014). Reordered 25 references by first citation. Distinguished our percentile intervals from studentized bootstrap inference, and positive beta/volatility tilts from BAB.
- Pinned the numerical reproduction materials to commit e9dad1e28a7e2376caaf905476dd2fdc84f469a2. Removed an unsupported implication that the journal requires no external deposit. GitHub remains the chosen destination; no Zenodo deposit was created.

## Academic-humanizer change log

Two passes were applied to the revised prose. Removed the overlong DSR explanation from the main narrative, kept the selection assumptions in S12, named comparison targets explicitly and used direct descriptions of the tested horizons and model versions. These are the authorized scope clarifications above, not stylistic claims of stronger evidence. The prose pass preserved numerical values, uncertainty, formulas, defined terms and citation assignments. No unresolved CITATION NEEDED markers remain.

## Source checks

- Glasserman–Lin: Scopus publication 85184706164 confirms authors, 2024 publication and DOI 10.3905/jfds.2023.1.143. https://www.scopus.com/pages/publications/85184706164 ; original abstract https://arxiv.org/abs/2309.17322 .
- Sarkar–Vafa: SSRN 4754678 (28 June 2024) and author research abstract https://suproteem.is/ ; treated as a working paper, not an asserted journal publication.
- Ledoit–Wolf: author publication listing and PDF https://www.ledoit.net/Robust_Sharpe_2008.pdf ; J. Empirical Finance 15(5), 850–859, DOI 10.1016/j.jempfin.2008.03.002.
- Frazzini–Pedersen: publisher https://doi.org/10.1016/j.jfineco.2013.10.005 and author institution https://research.cbs.dk/en/publications/betting-against-beta/ ; J. Financial Economics 111(1), 1–25.

## Validation

Live Google Docs exported to DOCX/PDF. All 8 tables match manuscript.md cell for cell; changed paragraphs and new references match; citations first occur in order 1–25. All existing embedded media are unchanged. Twelve-page layout reviewed, including Figure 2 and table continuations. Tables 3, 4 and 6 were moved intact to the next column; Table 8 uses compact cell paragraphs. Historical source data, analysis code and all numerical outputs are unchanged.


## Author-requested removal of Povzetek — 16 November 2026

Removed the complete working Slovenian translation at the author’s request. English abstract and all other text, table cells and references are unchanged, verified against the live DOCX export. Academic-humanizer preservation review: no prose rewrite; no changes to the meaning of retained text; no citation flags. The template includes a Povzetek placeholder, but the submission guidelines do not explicitly require an author-supplied Slovenian translation at initial submission.
