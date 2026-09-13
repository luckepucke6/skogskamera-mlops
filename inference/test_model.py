"""
Kör en TFLite-modell mot en bild. Både CLI (test/felsökning) och `classify_image`/
`load_model` som `app.py` (FastAPI-tjänsten) återanvänder.
FÖRENKLING: modellen är generisk MobileNetV2 (ImageNet), inte djur/fågel-
specifik — duger för att testa kedjan, inte riktig artbestämning.
"""

import sys
import time
from pathlib import Path

import numpy as np
from PIL import Image

# ai_edge_litert = aktuell TFLite-interpreter från Google. tflite_runtime
# är föråldrat och saknar paket för moderna Python-versioner.
from ai_edge_litert.interpreter import Interpreter

MODEL_PATH = Path(__file__).parent / "models" / "1.tflite"
LABELS_PATH = Path(__file__).parent / "models" / "labels.txt"
TOP_K = 3


def load_labels(path: Path) -> list[str]:
    """En rad per klassindex, i samma ordning som modellens output-vektor."""
    return path.read_text().splitlines()


def load_model() -> tuple[Interpreter, list[str]]:
    """Laddar modell + labels en gång — anropas vid start av FastAPI-tjänsten, inte per bild."""
    interpreter = Interpreter(model_path=str(MODEL_PATH))
    interpreter.allocate_tensors()  # reserverar minne för in-/utdata, måste köras först.
    return interpreter, load_labels(LABELS_PATH)


def preprocess_image(image: Image.Image, input_shape: np.ndarray) -> np.ndarray:
    """
    Gör om en bild till det format modellen förväntar sig.

    Läser upplösningen från modellen istället för att hårdkoda den, så
    scriptet funkar även om modellen byts ut.
    """
    _, height, width, _channels = input_shape

    image = image.convert("RGB")  # RGB, aldrig RGBA/gråskala
    image = image.resize((int(width), int(height)))

    arr = np.asarray(image, dtype=np.float32)

    # Modellen är tränad med pixelvärden i [-1, 1], inte råa 0-255. Fel
    # normalisering kraschar inte, men ger tysta, felaktiga resultat.
    arr = (arr / 127.5) - 1.0

    # Modellen förväntar sig en batch, shape [1, H, W, 3], även för en bild.
    return np.expand_dims(arr, axis=0)


def classify_image(interpreter: Interpreter, labels: list[str], image: Image.Image) -> dict:
    """
    Klassar en redan öppnad bild. Returnerar topp-K klasser + ren inferenstid —
    det FastAPI-tjänsten skickar vidare som JSON och loggar till MLflow/Prometheus.
    """
    input_details = interpreter.get_input_details()[0]
    output_details = interpreter.get_output_details()[0]

    input_data = preprocess_image(image, input_details["shape"])
    interpreter.set_tensor(input_details["index"], input_data)

    # Mäter bara invoke() — resten (containerstart, modell-laddning) är fast overhead
    # som inte beror på val av modell/kvantisering.
    start = time.perf_counter()
    interpreter.invoke()
    inference_ms = (time.perf_counter() - start) * 1000

    # [0] tar bort batch-dimensionen — ger en platt vektor, en sannolikhet per klass.
    output = interpreter.get_tensor(output_details["index"])[0]

    # argsort sorterar stigande, [::-1] vänder till högst-först, sedan TOP_K.
    top_indices = np.argsort(output)[::-1][:TOP_K]
    top = [{"label": labels[idx], "confidence": float(output[idx])} for idx in top_indices]

    return {"top": top, "inference_ms": inference_ms}


def classify(image_path: str) -> None:
    """CLI-läge: skriver ut resultatet i samma format som tidigare (CI:s smoke-test läser detta)."""
    interpreter, labels = load_model()
    result = classify_image(interpreter, labels, Image.open(image_path))

    print(f"Inferens: {result['inference_ms']:.1f} ms")
    print(f"\nTopp {TOP_K} klasser för '{image_path}':")
    for rank, entry in enumerate(result["top"], start=1):
        print(f"  {rank}. {entry['label']:<25} {entry['confidence']:.1%}")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Användning: python test_model.py <sökväg-till-bild>")
        print("Exempel:    python test_model.py test-images/ekorre.jpg")
        sys.exit(1)

    classify(sys.argv[1])
