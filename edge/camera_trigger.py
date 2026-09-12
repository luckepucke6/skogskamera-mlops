"""
Kameran på Pi 3B+ upptäcker rörelse genom att jämföra bilder, inte via PIR-sensor —
lådan står bakom fönsterglas som blockerar PIR:ens IR-signal.
Testbart på Mac utan kamera — se test_camera_trigger.py.
"""

from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

import numpy as np
from PIL import Image

# Två strömmar från kameran: lores (liten, gråskala) för jämförelsen, main (full
# upplösning) för bilden vi faktiskt sparar. 1296x972 är OV5647:s binnade helbildsläge.
LORES_SIZE = (320, 240)
MAIN_SIZE = (1296, 972)

PIXEL_THRESHOLD = 25  # hur mycket en enskild pixel måste ändras (av 255) för att räknas.
MIN_CHANGED_FRACTION = 0.02  # hur stor andel av bilden som måste ändras för "rörelse".

# Efter en sparad bild ignoreras nästa COOLDOWN_FRAMES bilder — motsvarar PIR-sensorns
# fördröjningspotentiometer, fast i kod och deterministiskt.
COOLDOWN_FRAMES = 5
INTERVAL_S = 1.0

CAPTURES_DIR = Path(__file__).parent / "captures"


def detect_motion(
    prev: np.ndarray,
    curr: np.ndarray,
    pixel_threshold: int = PIXEL_THRESHOLD,
    min_changed_fraction: float = MIN_CHANGED_FRACTION,
) -> bool:
    """
    True om tillräckligt stor andel pixlar ändrats mer än pixel_threshold.

    FÖRENKLING: fasta trösklar, ingen bakgrundsmodell — vind i träd eller ändrat
    ljus kan ge falska träffar. Riktig lösning: bakgrundssubtraktion (t.ex. OpenCV MOG2).
    """
    diff = np.abs(curr.astype(int) - prev.astype(int))
    changed_fraction = (diff > pixel_threshold).mean()
    return bool(changed_fraction > min_changed_fraction)


def save_capture(image: Image.Image, save_dir: Path = CAPTURES_DIR) -> Path:
    """Sparar image som CAPTURES_DIR/<UTC-tid>.jpg — kontraktet mot inferens-steget."""
    save_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    dest = save_dir / f"{timestamp}.jpg"
    image.save(dest)
    return dest


class PiCamera:
    """
    Wrapper runt picamera2 — enda stället i modulen som rör riktig kamera-hårdvara.
    Importen sker här (inte i toppen av filen) så modulen går att importera på Mac.
    """

    def __init__(self) -> None:
        from picamera2 import Picamera2

        self.picam2 = Picamera2()
        config = self.picam2.create_video_configuration(
            main={"size": MAIN_SIZE},
            lores={"size": LORES_SIZE, "format": "YUV420"},
        )
        self.picam2.configure(config)
        self.picam2.start()

        import time

        time.sleep(2)  # låt auto-exponeringen stabiliseras innan vi litar på bilderna.

    def frames(self, interval_s: float = INTERVAL_S) -> Iterable[tuple[np.ndarray, Image.Image]]:
        import time

        width, height = LORES_SIZE
        while True:
            request = self.picam2.capture_request()
            try:
                # YUV420: de första height raderna av arrayen är gråskale-planet (Y).
                gray = request.make_array("lores")[:height, :width].copy()
                full = request.make_image("main")
            finally:
                request.release()
            yield gray, full
            time.sleep(interval_s)


def run(
    frames: Iterable[tuple[np.ndarray, Image.Image]],
    save_dir: Path = CAPTURES_DIR,
    cooldown_frames: int = COOLDOWN_FRAMES,
) -> None:
    """Väntar på rörelse i frames och sparar en bild per upptäckt händelse."""
    prev_gray = None
    cooldown = 0

    print("Väntar på rörelse (Ctrl+C för att avbryta)...")
    try:
        for gray, full in frames:
            if prev_gray is not None:
                if cooldown > 0:
                    cooldown -= 1
                elif detect_motion(prev_gray, gray):
                    path = save_capture(full, save_dir)
                    print(f"Rörelse upptäckt — bild sparad: {path}")
                    cooldown = cooldown_frames
            prev_gray = gray
    except KeyboardInterrupt:
        print("\nAvslutar.")


if __name__ == "__main__":
    run(PiCamera().frames())
