import json
import os
import re
from functools import lru_cache
from pathlib import Path

ARTIFACT_DIR = Path(os.getenv("ARTIFACT_DIR", "/app/artifacts"))
ARTIFACT_BUCKET = os.getenv("ARTIFACT_BUCKET", "")
ARTIFACT_PREFIX = os.getenv("ARTIFACT_PREFIX", "").strip("/")
ENABLE_GENERATION = os.getenv("ENABLE_GENERATION", "false").lower() == "true"
ANSWERABILITY_POLICY_PATH = Path(
    os.getenv(
        "ANSWERABILITY_POLICY_PATH",
        str(Path(__file__).with_name("answerability_policy.json")),
    )
)
DEFAULT_ANSWERABILITY_POLICY = {
    "max_threshold": 0.38,
    "mean_top3_threshold": 0.36,
    "support_threshold": 0.34,
    "min_support_sources": 2,
}


@lru_cache(maxsize=1)
def load_answerability_policy():
    policy = dict(DEFAULT_ANSWERABILITY_POLICY)

    if ANSWERABILITY_POLICY_PATH.exists():
        with open(ANSWERABILITY_POLICY_PATH) as f:
            raw = json.load(f)
        candidate = raw.get("selected_policy", raw)
        for key in policy:
            if key in candidate:
                policy[key] = candidate[key]

    policy["max_threshold"] = float(policy["max_threshold"])
    policy["mean_top3_threshold"] = float(policy["mean_top3_threshold"])
    policy["support_threshold"] = float(policy["support_threshold"])
    policy["min_support_sources"] = int(policy["min_support_sources"])
    return policy

ARTIFACTS = {
    "vehicles_clean.parquet": "processed/vehicles_clean.parquet",
    "review_documents.parquet": "processed/review_documents.parquet",
    "price_model.cbm": "artifacts/price_model.cbm",
    "model_improvement_metrics.json": "artifacts/model_improvement_metrics.json",
    "review_index.faiss": "artifacts/review_index.faiss",
    "rag_metrics.json": "artifacts/rag_metrics.json",
}

def _s3_key(relative_key):
    return f"{ARTIFACT_PREFIX}/{relative_key}" if ARTIFACT_PREFIX else relative_key

def ensure_artifacts():
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    paths = {name: ARTIFACT_DIR / name for name in ARTIFACTS}
    missing = [name for name, path in paths.items() if not path.exists()]
    if not missing:
        return paths
    if not ARTIFACT_BUCKET:
        raise RuntimeError("Missing local artifacts and ARTIFACT_BUCKET is not configured: " + ", ".join(missing))

    import boto3
    s3 = boto3.client("s3")
    for name in missing:
        try:
            s3.download_file(ARTIFACT_BUCKET, _s3_key(ARTIFACTS[name]), str(paths[name]))
        except Exception:
            if name == "rag_metrics.json":
                continue
            raise
    return paths

def normalize_model(value):
    value = str(value).lower().strip()
    value = re.sub(r"[^a-z0-9]+", " ", value)
    return re.sub(r"\s+", " ", value).strip()
