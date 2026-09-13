"""
Kör en TFLite-modell mot en testbild för att verifiera den isolerat.
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


def preprocess_image(image_path: Path, input_shape: np.ndarray) -> np.ndarray:
    """
    Gör om en bild till det format modellen förväntar sig.

    Läser upplösningen från modellen istället för att hårdkoda den, så
    scriptet funkar även om modellen byts ut.
    """
    _, height, width, _channels = input_shape

    img = Image.open(image_path).convert("RGB")  # RGB, aldrig RGBA/gråskala
    img = img.resize((int(width), int(height)))

    arr = np.asarray(img, dtype=np.float32)

    # Modellen är tränad med pixelvärden i [-1, 1], inte råa 0-255. Fel
    # normalisering kraschar inte, men ger tysta, felaktiga resultat.
    arr = (arr / 127.5) - 1.0

    # Modellen förväntar sig en batch, shape [1, H, W, 3], även för en bild.
    return np.expand_dims(arr, axis=0)


def classify(image_path: str) -> None:
    labels = load_labels(LABELS_PATH)

    interpreter = Interpreter(model_path=str(MODEL_PATH))
    # Reserverar minne för in-/utdata utifrån modellens grafstruktur — måste köras först.
    interpreter.allocate_tensors()

    input_details = interpreter.get_input_details()[0]
    output_details = interpreter.get_output_details()[0]

    input_data = preprocess_image(Path(image_path), input_details["shape"])

    interpreter.set_tensor(input_details["index"], input_data)

    # Mäter bara invoke() — resten (containerstart, modell-laddning) är fast overhead
    # som inte beror på val av modell/kvantisering.
    start = time.perf_counter()
    interpreter.invoke()
    elapsed_ms = (time.perf_counter() - start) * 1000
    print(f"Inferens: {elapsed_ms:.1f} ms")

    # [0] tar bort batch-dimensionen — ger en platt vektor, en sannolikhet per klass.
    output = interpreter.get_tensor(output_details["index"])[0]

    # argsort sorterar stigande, [::-1] vänder till högst-först, sedan TOP_K.
    top_indices = np.argsort(output)[::-1][:TOP_K]

    print(f"\nTopp {TOP_K} klasser för '{image_path}':")
    for rank, idx in enumerate(top_indices, start=1):
        confidence = output[idx]
        print(f"  {rank}. {labels[idx]:<25} {confidence:.1%}")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Användning: python test_model.py <sökväg-till-bild>")
        print("Exempel:    python test_model.py test-images/ekorre.jpg")
        sys.exit(1)

    classify(sys.argv[1])
