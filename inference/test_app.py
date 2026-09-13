"""
Testar FastAPI-tjänsten utan MLflow/Telegram — de env-variablerna är inte satta
i testmiljön, så app.py hoppar över de sinksen (se log_to_mlflow/notify_telegram).
"""

from pathlib import Path

from fastapi.testclient import TestClient

from app import app

client = TestClient(app)

TEST_IMAGE = Path(__file__).parent / "test-images" / "2a.jpg"


def test_health():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_classify_returns_top_species():
    with open(TEST_IMAGE, "rb") as f:
        response = client.post("/classify", files={"file": ("2a.jpg", f, "image/jpeg")})

    assert response.status_code == 200
    body = response.json()
    assert body["species"] == "ibex"
    assert body["confidence"] > 0
    assert body["inference_ms"] > 0
    assert len(body["top"]) == 3


def test_metrics_endpoint_reflects_classification():
    with open(TEST_IMAGE, "rb") as f:
        client.post("/classify", files={"file": ("2a.jpg", f, "image/jpeg")})

    response = client.get("/metrics")
    assert response.status_code == 200
    assert 'skogskamera_detections_total{species="ibex"}' in response.text
