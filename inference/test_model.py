"""
test_model.py — SKOG-002: kör en TFLite-bildklassificerare mot en testbild.

Syftet med det här scriptet är att verifiera att modellen faktiskt fungerar
INNAN vi bygger in den i en container (SKOG-003) eller kopplar in riktig
kamera på Pi 3B+ (SKOG-009/010). Att testa modellen isolerat här, utan Docker
och utan hårdvara, gör felsökning mycket enklare: om något är fel vet vi att
det är modellen/preprocessingen, inte något annat i pipelinen.

OBS (flaggad avvägning enligt CLAUDE.md): modellen i inference/models/1.tflite
är en generisk MobileNetV2 tränad på ImageNet (1000 vardagsobjekt + en
"background"-klass), INTE en djur/fågel-specifik klassificerare. Den kan
känna igen några djur som finns i ImageNet (t.ex. räv, hjort, vissa fåglar)
men saknar många svenska skogsarter. Den duger bra för att verifiera att
hela kedjan — ladda modell, preprocessa bild, tolka output — fungerar. En
riktig djur/fågel-modell (t.ex. tränad via transfer learning på en
djur/fågel-dataset) är ett senare steg.
"""

import sys
from pathlib import Path

import numpy as np
from PIL import Image

# ai_edge_litert är Googles aktuella, aktivt underhållna TFLite-interpreter.
# Det äldre paketet `tflite_runtime` (som många äldre tutorials pekar på)
# har inte fått nya byggen på länge och saknar färdiga paket för moderna
# Python-versioner — därför använder vi ai_edge_litert istället. API:t är
# i praktiken identiskt, så koden nedan ser ut precis som den skulle gjort
# med tflite_runtime.
from ai_edge_litert.interpreter import Interpreter

MODEL_PATH = Path(__file__).parent / "models" / "1.tflite"
LABELS_PATH = Path(__file__).parent / "models" / "labels.txt"
TOP_K = 3


def load_labels(path: Path) -> list[str]:
    """En rad per klassindex, i samma ordning som modellens output-vektor."""
    return path.read_text().splitlines()


def preprocess_image(image_path: Path, input_shape: np.ndarray) -> np.ndarray:
    """
    Gör om en godtycklig bild till exakt det format modellen förväntar sig.

    Vi läser upplösningen (input_shape) direkt från modellen istället för
    att hårdkoda 224x224 här. Byter vi modell senare till en med annan
    upplösning fortsätter scriptet fungera utan ändringar.
    """
    _, height, width, _channels = input_shape

    img = Image.open(image_path).convert("RGB")  # RGB, aldrig RGBA/gråskala
    img = img.resize((int(width), int(height)))

    arr = np.asarray(img, dtype=np.float32)

    # Den här varianten av MobileNetV2 är tränad med pixelvärden
    # normaliserade till intervallet [-1, 1], inte de råa 0-255-värdena en
    # bild normalt har. Matchar inte normaliseringen det modellen tränades
    # med körs inferensen på "fel" indata — koden kraschar inte, men
    # resultaten blir slumpmässiga/felaktiga. Det här är ett klassiskt
    # nybörjarmisstag vid ML-inferens: fel är ofta tyst, inte en krasch.
    arr = (arr / 127.5) - 1.0

    # Modellen förväntar sig en "batch" av bilder, dvs. shape [1, H, W, 3],
    # även när vi bara skickar in en enda bild. Vi lägger till den extra
    # batch-dimensionen först.
    return np.expand_dims(arr, axis=0)


def classify(image_path: str) -> None:
    labels = load_labels(LABELS_PATH)

    interpreter = Interpreter(model_path=str(MODEL_PATH))
    # allocate_tensors() reserverar minnet för in-/utdata utifrån modellens
    # grafstruktur. Måste köras en gång innan man kan köra någon inferens.
    interpreter.allocate_tensors()

    input_details = interpreter.get_input_details()[0]
    output_details = interpreter.get_output_details()[0]

    input_data = preprocess_image(Path(image_path), input_details["shape"])

    interpreter.set_tensor(input_details["index"], input_data)
    interpreter.invoke()  # kör själva inferensen genom modellgrafen

    # [0] tar bort batch-dimensionen igen — vi vill ha en platt vektor med
    # 1001 sannolikheter, en per klass.
    output = interpreter.get_tensor(output_details["index"])[0]

    # np.argsort sorterar i STIGANDE ordning (lägst först). Vi vänder på
    # listan med [::-1] för att få högst sannolikhet först, och tar sedan
    # de TOP_K högsta.
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
