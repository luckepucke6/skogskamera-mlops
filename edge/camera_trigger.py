"""
edge/camera_trigger.py — SKOG-005: PIR-sensor → bildinfångning.

Det här är logiken som ska köra på Pi 3B+ (edge-noden): en PIR-sensor
(HC-SR501) känner rörelse, och när den gör det tar vi en bild och sparar
den. Kopplingen till nästa steg (inferens-containern, SKOG-003) beskrivs
längre ner — vi bygger INTE ihop det anropet än, se motivering där.

Körs som fristående script på Pi 3B+ (`python camera_trigger.py`), men går
även att testa på Mac utan riktig GPIO/kamera — se test_camera_trigger.py.
"""

from datetime import datetime, timezone
from pathlib import Path
from signal import pause
from typing import Callable

from gpiozero import MotionSensor

# gpiozero: ett Python-bibliotek som ger enkla klasser (MotionSensor, LED,
# Button, ...) ovanpå GPIO-pinnarna, istället för att man själv måste peka
# ut register och pull-up/pull-down-lägen med RPi.GPIO direkt. MotionSensor
# passar PIR-sensorer som HC-SR501 rakt av: man får en callback
# (`when_motion`) istället för att själv behöva polla pinnen i en loop.

PIR_GPIO_PIN = 4  # BCM-pinne för HC-SR501:s OUT-ben. Verifieras i SKOG-009
# när sensorn faktiskt kopplas in — just nu är det en rimlig platshållare.

CAPTURES_DIR = Path(__file__).parent / "captures"

# --- Handoff-design (del av SKOG-005s uppgift att definiera detta) --------
#
# Varje infångad bild sparas som CAPTURES_DIR/<UTC-tidsstämpel>.jpg. Det är
# hela kontraktet mot inferens-steget: en katalog med bildfiler, namngivna
# efter fångst-tid.
#
# Vi bygger INTE ihop själva anropet till inferens-containern här (t.ex. ett
# `docker run inference <sökväg>`). Det görs i SKOG-010, när koden faktiskt
# ska köras på Pi 3B+. Anledningen är dels att hålla edge/ och inference/
# oberoende av varandra (se CLAUDE.md), dels att vi ännu inte vet den
# exakta formen — subprocess-anrop till en lokal image, en lätt HTTP-tjänst,
# eller ett schemalagt jobb via k3s beror på hur SKOG-008/011 landar. Att
# bestämma det i detalj redan nu vore att gissa i onödan.
# ---------------------------------------------------------------------------


def capture_image(save_dir: Path = CAPTURES_DIR) -> Path:
    """
    Ta en bild och spara den i save_dir. Returnerar sökvägen till filen.

    OBS (flaggad avvägning, se CLAUDE.md om att flagga förenklingar): den
    riktiga implementationen på Pi 3B+ kommer använda `picamera2` mot
    InnoMaker OV5647-kameran (SKOG-009/010). picamera2 kräver Pi:ns
    kamerastack (libcamera) och kan varken installeras eller köras på Mac.
    Den här platshållaren simulerar en kamera genom att kopiera en av
    testbilderna vi redan har i inference/test-images/ (samma bilder som
    SKOG-002/003 verifierade fungerar med modellen). Det låter oss testa
    HELA trigger-flödet (PIR → "kamera" → sparad fil) redan nu, utan att
    vänta på fysisk montering.
    """
    save_dir.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    dest = save_dir / f"{timestamp}.jpg"

    # TODO (SKOG-010): byt ut raden nedan mot en riktig picamera2-infångning.
    dummy_source = Path(__file__).parent.parent / "inference" / "test-images" / "2a.jpg"
    dest.write_bytes(dummy_source.read_bytes())

    return dest


def build_sensor(pir_pin: int, capture: Callable[[], Path]) -> MotionSensor:
    """
    Skapar PIR-sensor-objektet och kopplar på capture-funktionen som
    callback vid rörelse.

    Utbruten som egen funktion (istället för att ligga inline i run()) så
    att testerna kan koppla in en låtsas-capture-funktion och en
    låtsas-pinne (MockFactory) utan att behöva starta hela den blockerande
    väntloopen i run().
    """
    pir = MotionSensor(pir_pin)

    def on_motion() -> None:
        path = capture()
        print(f"Rörelse upptäckt — bild sparad: {path}")

    pir.when_motion = on_motion
    return pir


def run(pir_pin: int = PIR_GPIO_PIN, capture: Callable[[], Path] = capture_image) -> None:
    """
    Startar PIR-bevakningen och blockerar sedan för alltid (tills
    Ctrl+C). Motsvarar den vanliga gpiozero-idiomen: sätt en callback med
    `when_motion`, kalla sedan på `pause()` — gpiozero hanterar rörelse-
    events i en bakgrundstråd, så huvudtråden behöver bara vänta.
    """
    build_sensor(pir_pin, capture)

    print(f"Väntar på rörelse på GPIO {pir_pin} (Ctrl+C för att avbryta)...")
    try:
        pause()
    except KeyboardInterrupt:
        print("\nAvslutar.")


if __name__ == "__main__":
    run()
