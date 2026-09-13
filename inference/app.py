"""
FastAPI-tjänst runt TFLite-modellen: tar emot en bild, klassar den, och loggar i
bakgrunden till MLflow + skickar en Telegram-notis. Långlivad process istället för
`docker run` per bild — modellen laddas en gång (se CLAUDE.md för varför).
"""

import io
import logging
import os
import time

import mlflow
import requests
from fastapi import BackgroundTasks, FastAPI, File, UploadFile
from PIL import Image
from prometheus_client import Counter, Gauge, Histogram, make_asgi_app

from test_model import classify_image, load_model

logger = logging.getLogger("skogskamera")

MLFLOW_TRACKING_URI = os.environ.get("MLFLOW_TRACKING_URI", "")
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "")
TELEGRAM_MIN_INTERVAL_S = float(os.environ.get("TELEGRAM_MIN_INTERVAL_S", "60"))

if MLFLOW_TRACKING_URI:
    mlflow.set_tracking_uri(MLFLOW_TRACKING_URI)
    mlflow.set_experiment("skogskamera")

# Prometheus-metrics — skrapas av Prometheus på /metrics, se infra/monitoring/prometheus.yaml.
DETECTIONS = Counter(
    "skogskamera_detections_total", "Antal klassificerade bilder, per art", ["species"]
)
INFERENCE_SECONDS = Histogram(
    "skogskamera_inference_seconds", "Ren inferenstid (interpreter.invoke), i sekunder"
)
LAST_CONFIDENCE = Gauge("skogskamera_last_confidence", "Konfidens för senaste detektionen")
SINK_ERRORS = Counter(
    "skogskamera_sink_errors_total", "Fel vid loggning till MLflow/Telegram", ["sink"]
)

app = FastAPI()
app.mount("/metrics", make_asgi_app())

interpreter, labels = load_model()

_last_telegram_sent = 0.0  # monotonic-tid för enkel takt-begränsning, se notify_telegram.


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


@app.post("/classify")
async def classify(background_tasks: BackgroundTasks, file: UploadFile = File(...)) -> dict:
    image_bytes = await file.read()
    image = Image.open(io.BytesIO(image_bytes))

    result = classify_image(interpreter, labels, image)
    top = result["top"][0]
    species, confidence = top["label"], top["confidence"]

    DETECTIONS.labels(species=species).inc()
    INFERENCE_SECONDS.observe(result["inference_ms"] / 1000)
    LAST_CONFIDENCE.set(confidence)

    # Svaret skickas direkt — MLflow/Telegram får inte fördröja triggerns loop på Pi 3B+.
    background_tasks.add_task(log_to_mlflow, species, confidence, result["inference_ms"], image_bytes)
    background_tasks.add_task(notify_telegram, species, confidence, image_bytes)

    return {
        "species": species,
        "confidence": confidence,
        "inference_ms": result["inference_ms"],
        "top": result["top"],
    }


def log_to_mlflow(species: str, confidence: float, inference_ms: float, image_bytes: bytes) -> None:
    """Körs i bakgrunden. Hoppas över helt om MLFLOW_TRACKING_URI saknas (t.ex. i tester)."""
    if not MLFLOW_TRACKING_URI:
        return
    try:
        with mlflow.start_run():
            mlflow.log_params({"species": species})
            mlflow.log_metrics({"confidence": confidence, "inference_ms": inference_ms})
            mlflow.log_image(Image.open(io.BytesIO(image_bytes)), "capture.jpg")
    except Exception:
        logger.exception("MLflow-loggning misslyckades")
        SINK_ERRORS.labels(sink="mlflow").inc()


def notify_telegram(species: str, confidence: float, image_bytes: bytes) -> None:
    """
    Körs i bakgrunden. FÖRENKLING: takt-begränsad till en notis per
    TELEGRAM_MIN_INTERVAL_S oavsett art — inte "bara vid nya arter".
    """
    global _last_telegram_sent
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        return

    now = time.monotonic()
    if now - _last_telegram_sent < TELEGRAM_MIN_INTERVAL_S:
        return

    try:
        requests.post(
            f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendPhoto",
            data={"chat_id": TELEGRAM_CHAT_ID, "caption": f"🦌 {species} ({confidence:.0%})"},
            files={"photo": ("capture.jpg", image_bytes, "image/jpeg")},
            timeout=10,
        )
        _last_telegram_sent = now
    except Exception:
        logger.exception("Telegram-notis misslyckades")
        SINK_ERRORS.labels(sink="telegram").inc()
