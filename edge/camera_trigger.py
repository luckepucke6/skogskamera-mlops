"""
PIR-sensor (HC-SR501) på Pi 3B+ känner rörelse och tar en bild.
Körs som script på Pi 3B+, men går att testa på Mac utan GPIO — se test_camera_trigger.py.
"""

from datetime import datetime, timezone
from pathlib import Path
from signal import pause
from typing import Callable

from gpiozero import MotionSensor

# gpiozero ger enkla klasser (MotionSensor m.fl.) ovanpå GPIO-pinnarna.
# MotionSensor ger en callback (when_motion) istället för att vi själva pollar pinnen.

PIR_GPIO_PIN = 4  # BCM-pinne för HC-SR501:s OUT-ben — platshållare tills sensorn kopplas in.

CAPTURES_DIR = Path(__file__).parent / "captures"

# Handoff till inferens: bilden sparas som CAPTURES_DIR/<UTC-tid>.jpg, det är
# kontraktet mot nästa steg. Själva anropet (docker run/HTTP/k3s-jobb?) byggs
# inte ihop här — formen är inte bestämd, och edge/ ska hållas oberoende av inference/.


def capture_image(save_dir: Path = CAPTURES_DIR) -> Path:
    """
    Ta en bild och spara den i save_dir. Returnerar sökvägen till filen.

    FÖRENKLING: riktig kamera (picamera2) kräver Pi:ns kamerastack och går inte
    att köra på Mac. Här kopieras istället en testbild från inference/test-images/,
    så hela trigger-flödet går att testa redan nu.
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
    Skapar PIR-sensorn och kopplar in capture som callback vid rörelse.

    Egen funktion (inte inline i run()) så testerna kan mocka capture och
    pinnen utan att starta run()s blockerande väntloop.
    """
    pir = MotionSensor(pir_pin)

    def on_motion() -> None:
        path = capture()
        print(f"Rörelse upptäckt — bild sparad: {path}")

    pir.when_motion = on_motion
    return pir


def run(pir_pin: int = PIR_GPIO_PIN, capture: Callable[[], Path] = capture_image) -> None:
    """
    Startar PIR-bevakningen och blockerar sedan tills Ctrl+C.
    gpiozero hanterar rörelse-events i en bakgrundstråd, så vi bara väntar.
    """
    build_sensor(pir_pin, capture)

    print(f"Väntar på rörelse på GPIO {pir_pin} (Ctrl+C för att avbryta)...")
    try:
        pause()
    except KeyboardInterrupt:
        print("\nAvslutar.")


if __name__ == "__main__":
    run()
