import logging
import os
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from .schemas import AskRequest, AskResponse, PriceRequest, PriceResponse
from .services import (
    ENABLE_GENERATION,
    get_price_engine,
    get_rag_engine,
    load_answerability_policy,
    load_public_metrics,
    load_vehicle_catalog,
)

logger = logging.getLogger(__name__)

app = FastAPI(
    title="Auto Market Assistant API",
    version="1.0.0",
    description="CatBoost asking-price context plus grounded owner-review retrieval.",
)

origins = [
    item.strip()
    for item in os.getenv(
        "ALLOWED_ORIGINS",
        "https://gnambood.github.io,http://localhost:8000,http://localhost:3000",
    ).split(",")
    if item.strip()
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=False,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)

@app.get("/health")
def health():
    return {
        "status": "ok",
        "service": "auto-market-assistant",
        "generation_enabled": ENABLE_GENERATION,
        "answerability_policy": load_answerability_policy(),
    }

@app.get("/metrics")
def metrics():
    try:
        return load_public_metrics()
    except Exception as exc:
        logger.exception("metrics failed")
        raise HTTPException(status_code=503, detail="Service temporarily unavailable") from exc

@app.get("/catalog")
def catalog():
    try:
        return load_vehicle_catalog()
    except Exception as exc:
        logger.exception("catalog failed")
        raise HTTPException(status_code=503, detail="Service temporarily unavailable") from exc

@app.post("/predict-price", response_model=PriceResponse)
def predict_price(payload: PriceRequest):
    try:
        return get_price_engine().predict(payload)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except Exception as exc:
        logger.exception("price inference failed")
        raise HTTPException(status_code=503, detail="Service temporarily unavailable") from exc

@app.post("/ask", response_model=AskResponse)
def ask(payload: AskRequest):
    try:
        return get_rag_engine().ask(payload)
    except Exception as exc:
        logger.exception("review retrieval failed")
        raise HTTPException(status_code=503, detail="Service temporarily unavailable") from exc
