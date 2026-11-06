# Auto Market Assistant

A Python project for exploring historical vehicle asking prices and owner-reported experiences. It combines a CatBoost regression model, review retrieval, and a batch data pipeline.

[Portfolio demo](https://gnambood.github.io/auto-market-assistant.html) · [Model card](MODEL_CARD.md) · [Architecture](ARCHITECTURE.md) · [Data pipeline](DATA_PIPELINE.md) · [Deployment notes](DEPLOY_AWS.md)

## What I built

- **Price estimation:** CatBoost regression trained on 238,959 vehicle listings; tested on a chronological holdout.
- **Owner-review retrieval:** MiniLM embeddings and FAISS over 70,665 matched reviews, with citation checks and an evidence fallback.
- **Data pipeline:** Python batch ETL, partitioned Parquet, validation gates, and SHA-256 manifests.
- **Application:** FastAPI and Docker, with an AWS ECS deployment path and GitHub Actions checks.
- **Historical analysis:** Descriptive asking-price and listing-volume trends with data-coverage and sample-size safeguards.

## Evaluation at a glance

| Component | Result | Evaluation context |
| --- | --- | --- |
| Price model | MAE $2,866; R² 0.883 | Chronological holdout on historical listings |
| Price model | 84.9% within ±$5,000 | Same held-out vehicle listings |
| Review retrieval | Hit@5 81.67%; MRR@10 0.6256 | Vehicle-identity retrieval benchmark |
| Answerability | Precision 90.0%; recall 84.38%; F1 87.10% | Held-out, weakly supervised benchmark across unseen vehicle families |

These metrics describe different tasks and should not be combined into a single system-accuracy claim. Price estimates reflect **2021 Craigslist asking prices**, not completed transactions or current market valuations. The live API uses retrieval-backed answers with generation disabled; Qwen generation was evaluated separately in the notebook.

## Research experiments and current scope

The project continued to evolve **after the first working price-and-reviews demo** through separate evaluation tracks: baseline versus selected CatBoost, retrieval ranking, answerability and abstention, data reconstruction, and descriptive market intelligence. These are research **workstreams**, not a claim that their experiments ran concurrently. Reported historical metrics, new fixture-based tests and still-proposed experiments are labeled separately in [the experiment ledger](research/EXPERIMENTS.md).

The maintained [market-trends module](pipelines/market_trends.py) now computes monthly historical asking-price summaries and observed daily listing counts by make, model family and vehicle year. It includes duplicate/date checks and minimum-sample safeguards. **Real-dataset trend validation is still pending**; results are not current market valuations or forecasts.

For a reversible, low-cost serving plan see [AWS pause and cost checklist](operations/AWS_PAUSE_PLAN.md). AWS ECS task compute was paused on 2026-11-06 (desired/running 0, scaling 0–0); S3, ECR, Athena and the load balancer remain. See the pause runbook for restoration.

## Running research experiments offline

New standalone experiments use pinned Python 3.11 dependencies from `requirements-research.txt`. [Research commands](research/README.md) cover a strictly chronological median-price baseline and feature-contribution analysis on a saved CatBoost model. These are **new, locally testable methods**, not fabricated reproductions of historical training runs. The raw data, exact original train/test split and model artifacts are required to replicate the published CatBoost results.

The API is kept in small modules (`runtime`, `price_engine`, `review_engine`, and a stable `services` facade). The updated RAG policy never borrows reviews from another model when evidence is sparse. [Reproducibility limitations](research/EXPERIMENTS.md) and the [AWS pause plan](operations/AWS_PAUSE_PLAN.md) remain explicit.

## Reading the repository

| Location | Purpose |
| --- | --- |
| `api/` | FastAPI endpoints and inference services |
| `pipelines/` | Batch processing and data-quality checks |
| `tests/` | API and pipeline regression tests |
| `infra/`, `deploy/` | Reference infrastructure and deployment assets |
| `sql/` | Athena validation queries |
| `metrics/`, `reproducibility/` | Evaluation records and supporting evidence |

The data platform, serving architecture, and deployment setup are documented separately so the main README stays readable.

## Live production deployment

The current deployment uses:

- GitHub Pages for the portfolio UI
- FastAPI for inference endpoints
- Docker for the application image
- Amazon ECR for private image storage and scan-on-push
- Amazon ECS Express Mode / Fargate for serving
- an AWS-managed HTTPS ingress/load-balancing layer
- Amazon S3 for model, FAISS, metrics and processed-data artifacts
- private/versioned S3 storage with public-access blocking
- IAM task, execution and infrastructure roles
- GitHub Actions OIDC federation to AWS instead of long-lived deployment keys
- deployment smoke tests that verify the active ECS image and calibrated RAG policy

For the full AWS resource inventory, security model, CI/CD flow, runtime configuration and production/reference-infrastructure distinction, see **[DEPLOY_AWS.md](DEPLOY_AWS.md)**, **[ARCHITECTURE.md](ARCHITECTURE.md)** and **[DATA_PIPELINE.md](DATA_PIPELINE.md)**.

Live API:

`https://au-31cea16fe69c481c8dd923a37b6252df.ecs.ca-central-1.on.aws`

Endpoints:
- `POST /predict-price`
- `POST /ask`
- `GET /health`
- `GET /metrics`

The cloud service intentionally runs with `ENABLE_GENERATION=false`, so the live `/ask` endpoint returns deterministic retrieval-backed evidence. The final notebook separately validates Qwen generation with short source aliases, citation mapping, and fallback.

The production RAG path is now:

```text
scope/capability guard
        ↓
vehicle-family/year filtering
        ↓
question-only MiniLM retrieval
        ↓
calibrated multi-signal evidence gate
        ↓
grounded evidence response
        ↓
citation validation
```

## Data engineering layer

The validated notebook transformations have been refactored into a reusable batch pipeline under `pipelines/`.

It produces manufacturer-partitioned Parquet datasets, row-level cleaning audits, data-quality reports, quality gates and SHA-256 lineage manifests so CatBoost, RAG and analytics can share one curated definition of the data.

```text
raw CSV snapshots
      ↓
Python batch ETL
      ↓
schema + quality gates
      ↓
curated Parquet in S3
      ↓
├── CatBoost
├── FAISS / RAG
└── Glue Data Catalog → Athena → Tableau / QA
```

A deployable Glue/Athena catalog stack is defined in `infra/data-catalog-template.yaml`, with reusable Athena queries in `sql/`. The analytics stack was deployed separately on 2026-10-08 as CloudFormation stack `auto-market-data-platform` in `ca-central-1`. Both tables (`vehicles`, `reviews`) passed Athena row-count and content queries. It is not auto-deployed with ECS because Athena/Glue usage can incur AWS charges. Raw-source ingestion and reproducible end-to-end lineage are still pending.

See **[DATA_PIPELINE.md](DATA_PIPELINE.md)** for the ETL rules, S3 layout, lineage model, quality thresholds and catalog setup.

## S3 layout

```text
raw/
  craigslist/
  edmunds/

curated/
  vehicles/manufacturer=.../
  reviews/manufacturer=.../
  vehicle_review_matches/manufacturer=.../

quality/
  vehicle_cleaning_audit.csv
  vehicle_quality.json
  review_quality.json
  quality_gate.json

manifests/
  pipeline_<source-fingerprint>.json
  latest.json

processed/
  vehicles_clean.parquet
  review_documents.parquet

artifacts/
  price_model.cbm
  model_improvement_metrics.json
  review_index.faiss
  rag_metrics.json
```

## Website behavior

The portfolio tries the live AWS API first. If the cloud request is unavailable or times out, it falls back to verified static output, so the demo remains usable even when compute is offline.

## Reproducing the portfolio data

1. Run the final Part 1 notebook and save `part1_artifacts.zip`.
2. Run the final Part 2 notebook using that fresh Part 1 bundle and save `part2_artifacts.zip`.
3. Upload the six deployment artifacts to the expected S3 paths.
4. Use `src/build_demo_json_from_artifacts.py` when a larger precomputed fallback set is needed.
5. Deploy the Docker API through ECR + ECS Express Mode.

## Large artifacts

Large Parquet files, FAISS indexes, embeddings, model binaries and ZIP bundles are intentionally excluded from Git. The live API loads its artifacts from S3.

## Scope and limitations

- Price outputs represent 2021 Craigslist asking-price context.
- Asking price is not a completed transaction price.
- Results should not be interpreted as current vehicle valuations.
- Retrieval Hit@k/MRR metrics evaluate vehicle-identity retrieval behavior, not universal semantic answer quality.
- The answerability metrics come from a weakly supervised held-out benchmark and should not be treated as a universal RAG score.
- Owner reviews are anecdotal and may disagree.

## Future work

The next research-oriented improvements would be:

- build a manually labelled gold set of question-review pairs for direct relevance grading,
- compare MiniLM dense retrieval with cross-encoder reranking on the same labels,
- test passage/sentence chunking instead of whole-review embeddings,
- compare newer retrieval embeddings such as BGE or E5 using the same benchmark,
- add claim-level faithfulness/entailment evaluation for generated answers,
- evaluate whether a managed or larger production generator improves synthesis enough to justify additional latency and infrastructure cost.

These are intentionally left as future work because the current portfolio goal is an end-to-end, production-oriented ML system rather than a RAG research benchmark.
