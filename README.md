# Auto Market Assistant

**An end-to-end used-vehicle ML application:** historical asking-price estimates, evidence-backed owner reviews, and a validated data pipeline behind a FastAPI service.

[**View the portfolio demo**](https://gnambood.github.io/auto-market-assistant.html) · [System architecture](ARCHITECTURE.md) · [Model card](MODEL_CARD.md) · [Data pipeline](DATA_PIPELINE.md)

> **Demo status (November 2026):** The public portfolio includes a precomputed, verified Ford F-150 example. AWS inference is temporarily paused to avoid continuous Fargate charges. The application code, trained artifacts and documented deployment are retained; the demo is **not** presenting new live predictions while the service is paused.

## What it does

A car's listing price and its owners' experiences answer different questions. Auto Market Assistant keeps them separate:

1. **Historical asking-price estimate** — CatBoost predicts an asking price from the vehicle's make, model, year, mileage and available condition details. The response also includes comparable-listing statistics and their support count.
2. **Evidence-backed owner reviews** — MiniLM embeddings and FAISS retrieve Edmunds reviews for the selected model family. An answerability policy filters weak evidence and returns source IDs or an abstention. The CPU-serving API uses retrieval-based responses, without an always-on LLM.
3. **Market context** — a batch analysis computes historical asking-price summaries and observed listing volumes by make, model family, vehicle year and posting date. This is descriptive analysis, not a forecast or part of CatBoost inference.

The project includes preprocessing, validation, saved models, serving code, a browser-facing demo, tests, Docker and AWS deployment infrastructure.

## System, end to end

```text
Craigslist listing CSVs          Edmunds owner-review CSVs
            \                           /
             `--- Python cleaning + data-quality gates
                            |
                  Curated Parquet on S3
                     /       |        \
              CatBoost   MiniLM/FAISS  Glue / Athena
                     \       /          (analytics)
                      FastAPI + Docker
                            |
                     GitHub Pages demo
                  (saved example while
                     AWS is paused)
```

- **`pipelines/`** prepares and validates vehicle and review data, produces manufacturer-partitioned Parquet and tracks data lineage with SHA-256.
- **`api/`** serves price inference, review retrieval, the vehicle catalog and public model metrics. It enforces input validation, model-family scoping and explicit abstention.
- **`metrics/`** contains recorded evaluation results; **`tests/`** covers data processing, API behavior, market trends and edge cases.
- **`sql/`** contains Athena queries. **`infra/`**, **`lambda/`** and **`deploy/`** document cloud components and deployment.
- **`src/`** contains artifact upload and demo-export scripts; **`reproducibility/`** preserves the independent data-reconstruction record.
- **`research/`** contains optional offline baselines and explainability tools, separate from the app's serving path.

The GitHub Pages frontend is maintained in [the portfolio repository](https://github.com/gnambood/gnambood.github.io); the Python application and data pipeline live here.

## Measured results

| Component | Recorded result | What it measures |
| --- | --- | --- |
| CatBoost | **$2,866 MAE**, **0.883 R²** | Historical asking-price regression on a chronological holdout |
| CatBoost | **84.86%** | Test examples within ±$5,000 |
| MiniLM + FAISS | **81.67% Hit@5**, **0.6256 MRR@10** | Vehicle-identity retrieval on 60 evaluation questions |
| Answerability guard | **87.10% F1**, **90.0% precision** | Held-out *weakly supervised* accept/abstain evaluation |

These are different evaluations, not one combined accuracy score. The training/evaluation results are preserved as reported artifacts; the exact original training notebooks and split IDs are not bundled in this repository. See [the model card](MODEL_CARD.md) for methodology and limitations.

**Data coverage:** 238,959 curated historical vehicle listings and 70,665 matched owner reviews. The source listings are from the **2021** market; estimated asking prices are **not** current appraisals or completed sale prices.

## Run the application locally

You can run the serving stack without AWS once you have the saved artifact bundle.

```bash
git clone https://github.com/gnambood/auto-market-assistant.git
cd auto-market-assistant

# Place the exported files under ./artifacts:
# vehicles_clean.parquet, review_documents.parquet,
# price_model.cbm, model_improvement_metrics.json,
# review_index.faiss, rag_metrics.json (optional)

docker build -t auto-market-assistant .
docker run --rm -p 8080:8080 \
  -e ARTIFACT_DIR=/app/artifacts \
  -e ENABLE_GENERATION=false \
  -v "$PWD/artifacts:/app/artifacts" \
  auto-market-assistant
```

Then visit [http://localhost:8080/docs](http://localhost:8080/docs) for the interactive API documentation or check [http://localhost:8080/health](http://localhost:8080/health).

| Endpoint | Purpose |
| --- | --- |
| `GET /health` | API status and answerability policy |
| `GET /catalog` | Supported makes, models and inputs |
| `POST /predict-price` | Historical price and comparable statistics |
| `POST /ask` | Retrieved review evidence or explicit abstention |
| `GET /metrics` | Saved model/retrieval evaluation metadata |

The large model, review index and datasets are intentionally not committed to Git. See [deployment notes](DEPLOY_AWS.md) for S3 paths and artifact setup. Without the artifacts, model-dependent endpoints cannot run.

## Build the curated datasets

With the original source CSVs available:

```bash
python -m pip install -r requirements-data.txt
python -m pipelines.run_pipeline \
  --vehicles-csv /path/to/vehicles.csv \
  --reviews-dir /path/to/edmunds-reviews \
  --output-dir ./data-platform-output
```

The pipeline validates required fields and cleaning gates, writes Parquet/quality reports and produces a manifest containing input hashes, transformation-code hashes, settings and output checksums. [Data pipeline details](DATA_PIPELINE.md).

To execute the included regression suite:

```bash
python -m pip install -r requirements-research.txt
python -m pip install fastapi==0.115.6 pydantic==2.10.4 httpx==0.28.1 ruff==0.8.4
ruff check api pipelines research tests
python -m pytest -q
```

The latest verified GitHub CI run on the development branch passed **47 tests** and Ruff lint. See [CI](https://github.com/gnambood/auto-market-assistant/actions/workflows/auto-market-ci.yml).

## Deployment and demo status

The application was deployed as a CPU-based FastAPI container using Amazon ECR, ECS Express Mode/Fargate, private S3 model artifacts and GitHub Actions with OIDC. Its separate Glue/Athena layer supports data-quality and summary analytics.

On **November 6, 2026**, ECS task capacity was set to **zero** (desired 0; autoscaling minimum/maximum 0). The service configuration, S3 artifacts, ECR images and Athena catalog were preserved. The managed load balancer and stored artifacts may still incur charges. The public demo should use its saved, labeled example until cloud inference is deliberately restored.

[Deployment architecture](DEPLOY_AWS.md) · [AWS pause/restore runbook](operations/AWS_PAUSE_PLAN.md)

## Design choices and limits

- **Separate price prediction from language generation.** Review text does not change CatBoost's numerical prediction.
- **Prefer grounded retrieval and abstention.** Too little relevant evidence is a reason to decline an answer, not to substitute another model's reviews.
- **Batch, not streaming.** These are historical snapshots; Pandas/Parquet are sufficient without Spark or Kafka.
- **Show evidence and dataset scope.** Comparables, review IDs and dates are part of the response, not hidden implementation details.
- **Treat model explanations as contributions, not causes.** Optional CatBoost SHAP analysis is available in [`research/`](research/README.md), but it does not prove causal price drivers.
- **Avoid overclaiming reproducibility.** The recorded raw-to-Parquet reconstruction and current test suite are available; independently reproducing the historical model training requires the original final training notebooks and frozen split definitions.

The result is a complete **historical ML inference and review-evidence application**, with a reproducible data-processing layer and optional cloud serving. It is not a real-time vehicle market data provider.
