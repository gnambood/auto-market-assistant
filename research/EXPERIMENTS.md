# Parallel research experiments and reproducibility record

This ledger reconstructs the project's **post-build investigative workstreams** from the two Git repositories and recorded evaluation artifacts. "Parallel" means distinct scientific questions pursued around the same application, not proof that training jobs ran simultaneously. Reported historical numbers have **not** been rerun in this branch.

Source repositories: [standalone project](https://github.com/gnambood/auto-market-assistant) and [original portfolio repository](https://github.com/gnambood/gnambood.github.io). This record was prepared from standalone main commit `e556189` (2026-11-04). A Git commit date is not necessarily the date an experiment was executed.

## Research questions

1. How much can structured vehicle features improve estimates of **historical Craigslist asking prices** under a chronological holdout?
2. Can a filtered owner-review index retrieve relevant vehicle evidence while knowing when to abstain?
3. Can the available 2021 snapshot support descriptive posting-date trends without implying present-day values or forecasts?
4. Can the cleaned vehicle/review datasets be independently reconstructed and checked?

## Parallel experiment matrix

| ID | Workstream and comparison | Evaluation criterion | Recorded outcome | Evidence status |
| --- | --- | --- | --- | --- |
| P-01 | Initial price-model baseline (`v0_test`) | Historical asking-price error | MAE **$3,195.97**, RMSE **$5,413.62**, R² **0.8642** | **Reported**: [price metrics](../metrics/model_improvement_metrics.json). Training code and split row IDs not included in tracked repo. |
| P-02 | Selected **CatBoost V2** (depth 9, learning rate 0.03, 2,200 iterations) | Same documented chronological test task, compared to P-01 | MAE **$2,866.34**, RMSE **$5,019.51**, R² **0.8832**, within ±$5,000 **84.86%**, relative MAE improvement **10.31%** | **Reported**: [price metrics](../metrics/model_improvement_metrics.json); exact training protocol not fully reconstructible here. |
| R-01 | MiniLM + FAISS identity retrieval | 60 vehicle-identity queries: Hit@k, MRR, nDCG | Hit@1 **50%**, Hit@3 **73.33%**, Hit@5 **81.67%**, MRR@10 **0.6256**, nDCG@10 **0.6883** | **Reported**: [RAG metrics](../metrics/rag_metrics.json). Identity matching is not answer-faithfulness accuracy. |
| R-02 | Calibrated answerability gate with scope and multi-signal review support | Held-out weakly supervised accept/abstain evaluation | Precision **90%**, recall **84.38%**, F1 **87.10%**, accuracy **80.95%** | **Reported**: [answerability policy](../api/answerability_policy.json); missing human-labeled gold set and threshold search trace. |
| R-03 | Retrieval-only production response versus optional Qwen generation | Citation formatting, grounded evidence and resource constraints | Live configuration has **generation disabled**; Qwen is separately described as tested in notebooks | **Architectural choice evidenced**, not a published controlled head-to-head generation benchmark. |
| D-01 | Reusable Pandas ETL, cleaning, validation and scoping | Row retention, input schema and source consistency | **426,880 → 348,506 → 238,959** vehicle listings; **137,660 → 102,546 → 70,665** reviews | **Reported**: [data-pipeline record](../DATA_PIPELINE.md). |
| D-02 | Archived DuckDB/Pandas reconstruction against reference Parquet | Bidirectional `EXCEPT ALL`, all columns, unique IDs and row counts | Rebuilt **238,959 vehicle** and **70,665 review** rows; zero differing rows reported | **Archived historical verification**: [reproducibility record](../reproducibility/README.md). This verifies data content, not retraining. |
| M-01 | Posting-month asking-price medians and daily observed listing volume | Date coverage, comparable groups, sample suppression, duplicate-ID/missing-date diagnostics | **Six synthetic-fixture tests passed** for the new module; no production-snapshot trend values asserted | **New implementation**: [market trends](../pipelines/market_trends.py) and [tests](../tests/test_market_trends.py). Earlier work described a viewer but its code is not on this standalone main. |
| M-02 | Forecasting versus a simple chronological baseline | Out-of-period forecasting error and coverage | **Not run**, deliberately excluded for insufficient historical coverage | **Proposed/deferred**, not a historical result. No SARIMA/Prophet metrics claimed. |

### Interpreting the comparisons

- P-01 and P-02 document a reported improvement but **do not isolate** the effect of a single feature. Feature ablations require the original training code and fixed holdout.
- R-01 is a ranking experiment; R-02 is a separate answerability/abstention experiment. They must not be combined into a single "RAG accuracy."
- R-03 is a serving design decision. The existence of Qwen experiments does not prove generation was more accurate, cheaper, or more faithful.
- D-02's full-content comparison is strong data validation, but depends on access to the historical raw inputs and reference artifacts.
- M-01 is newly written code; synthetic test passes **do not establish** meaningful temporal trends in the real 2021 data.

## Why these were parallel tracks after the working prototype

The initial application answered two user questions: an asking-price estimate and owner-review evidence. Separate follow-on investigations then improved **price-model error**, **review search and source identity**, **when to refuse weak evidence**, **data pipeline reliability**, and **historical market context**. Some work was recorded through model metrics, others through engineering commits and archived data comparisons. Treat them as distinct experiment tracks with different outcome measures, not an invented linear sequence of algorithms.

## Reproducibility: available versus missing

| Component | Reproducible from this repo now? | Missing evidence or command |
| --- | --- | --- |
| Cleaned curated datasets | Partly: maintained ETL and archived reconstruction scripts are present | Original snapshot access, Python/dependency lock, isolated staging/reference data and complete validation |
| CatBoost V0 → V2 | **No complete independent retrain** | Final Part 1 notebook/source, features, split dates and IDs, seeds, tuning search and frozen artifact hashes |
| MiniLM/FAISS evaluation | **No complete independent rebuild** | Original Part 2 notebook/source, stable review ordering, embedder revision, query labels and index-generation command |
| Answerability calibration | Runtime policy and some regression tests | Original weak-label procedure, family-wise held-out sets and threshold selection protocol |
| Market intelligence M-01 | New code with fixture tests only | Historical snapshot analysis, sample counts, actual month/day coverage, composition diagnostics and output manifest |
| Cloud demo | Deployed architecture documented separately | Verified offline fallback, live resource inventory, and a controlled, reversible AWS pause |

## Required scientific practice going forward

1. Keep **reported historical** results separate from **locally rerun** results and **proposed** experiments.
2. Preserve the 2026-10-10 archived scripts and hashes as evidence. Do not clean them in place; develop a portable entry point separately.
3. Freeze raw/curated snapshot SHA-256, transformation-code hash, config, dependency versions, model/index artifact checksums and row ordering.
4. Publish chronological split cutoffs and row counts, model features, seeds, baseline definitions and metric formulas.
5. Recompute P-01/P-02 on identical held-out rows before asserting a causal gain; use manually judged review evidence to validate R-01/R-02.
6. For M-01, report coverage, minimum samples, excluded groups and changes in vehicle mileage/condition composition. The time axis is **posting date**; `year` is the vehicle's manufacture-year cohort.
7. Keep the maintained implementation small and explicit. Avoid adding Spark, Kafka, generative models, or forecasting without measurement.

## Verified repository development chronology

- **2026-09-28:** original portfolio publishes the interactive Auto Market case study.
- **2026-10-01–03:** live catalog, custom questions, RAG guardrails, calibrated policy and deployment work.
- **2026-10-07:** reusable ETL and idempotent-rerun improvements.
- **2026-10-08:** Athena validation and descriptive analytics evidence recorded.
- **2026-10-10:** independent raw-to-Parquet reconstruction and lineage archived.
- **2026-10-14:** explicit vehicle-context mismatch guard and regression tests.
- **2026-10-29:** dedicated research repo extracted from the portfolio.
- **2026-11-04:** standalone README clarified through documentation-only PR.
- **2026-11-05:** M-01 monthly/daily descriptive functions added on this research branch; **new local test results, not historical experiments**.

The main price and RAG result artifacts predate this extracted repo; the exact dates of the original model-training experiments must be recovered from the source notebooks rather than inferred from commits.
