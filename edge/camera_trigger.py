"""
Kameran på Pi 3B+ upptäcker rörelse genom att jämföra bilder, inte via PIR-sensor —
lådan står bakom fönsterglas som blockerar PIR:ens IR-signal.
Testbart på Mac utan kamera — se test_camera_trigger.py.
"""

import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Iterable

import numpy as np
import requests
from PIL import Image, ImageFilter

# Två strömmar från kameran: lores (liten, gråskala) för jämförelsen, main (full
# upplösning) för bilden vi faktiskt sparar. 1296x972 är OV5647:s binnade helbildsläge.
LORES_SIZE = (320, 240)
MAIN_SIZE = (1296, 972)

# Env-läsbara så de kan justeras via systemd (Environment=) utan kodändring/omdeploy.
PIXEL_THRESHOLD = int(os.environ.get("PIXEL_THRESHOLD", "25"))  # hur mycket en pixel måste ändras.
MIN_CELL_FRACTION = float(os.environ.get("MIN_CELL_FRACTION", "0.5"))  # se motion_score.
CELL_SIZE = int(os.environ.get("CELL_SIZE", "40"))  # rutstorlek i pixlar, se motion_score.
BLUR_RADIUS = int(os.environ.get("BLUR_RADIUS", "2"))  # suddar bort bladflimmer/sensorbrus.

# Efter en sparad bild ignoreras nästa COOLDOWN_FRAMES bilder — motsvarar PIR-sensorns
# fördröjningspotentiometer, fast i kod och deterministiskt.
COOLDOWN_FRAMES = 5
INTERVAL_S = 1.0

CAPTURES_DIR = Path(__file__).parent / "captures"

# Tjänsten körs på samma Pi (Docker, port 8000) i normalfallet, se CLAUDE.md.
INFERENCE_URL = os.environ.get("INFERENCE_URL", "http://localhost:8000/classify")


def motion_score(
    prev: np.ndarray,
    curr: np.ndarray,
    pixel_threshold: int = PIXEL_THRESHOLD,
    cell_size: int = CELL_SIZE,
    blur_radius: int = BLUR_RADIUS,
) -> float:
    """
    Delar bilden i cell_size×cell_size-rutor och returnerar den mest ändrade rutans andel
    ändrade pixlar (0–1) — inte hela bildens andel.

    Varför: ett djur/en person är en kompakt klump som fyller en eller ett par rutor helt,
    medan vind i grenar och skuggor som rör sig ger utspridda, glesa ändringar över hela
    bilden. Uppmätt på riktiga bilder: vind gav max 0.21 i en enskild ruta, en person
    gående gav 0.79–1.00 — global andel för samma bilder låg för nära varandra (0.02–0.07)
    för att skilja dem åt. Blur:en (blur_radius) tar bort bladflimmer/sensorbrus innan
    jämförelsen, annars läcker enstaka rutor över tröskeln ändå.

    FÖRENKLING: fortfarande ingen riktig bakgrundsmodell (t.ex. OpenCV MOG2). Ett stort djur
    som står helt stilla ger inget utslag, och djur mindre än en ruta kan missas — medvetet,
    de går ändå inte att klassa på en så liten yta.
    """
    if blur_radius > 0:
        prev = np.array(Image.fromarray(prev.astype(np.uint8)).filter(ImageFilter.GaussianBlur(blur_radius)))
        curr = np.array(Image.fromarray(curr.astype(np.uint8)).filter(ImageFilter.GaussianBlur(blur_radius)))

    diff = np.abs(curr.astype(int) - prev.astype(int))
    mask = diff > pixel_threshold

    height, width = mask.shape
    trimmed_h, trimmed_w = (height // cell_size) * cell_size, (width // cell_size) * cell_size
    grid = mask[:trimmed_h, :trimmed_w].reshape(trimmed_h // cell_size, cell_size, trimmed_w // cell_size, cell_size)
    return float(grid.mean(axis=(1, 3)).max())


def detect_motion(prev: np.ndarray, curr: np.ndarray, min_cell_fraction: float = MIN_CELL_FRACTION) -> bool:
    """True om motion_score överstiger tröskeln — se motion_score för varför den mäts så."""
    return motion_score(prev, curr) > min_cell_fraction


def save_capture(image: Image.Image, save_dir: Path = CAPTURES_DIR) -> Path:
    """Sparar image som CAPTURES_DIR/<UTC-tid>.jpg — kontraktet mot inferens-steget."""
    save_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    dest = save_dir / f"{timestamp}.jpg"
    image.save(dest)
    return dest


def send_to_inference(image_path: Path, url: str = INFERENCE_URL) -> None:
    """
    Skickar en sparad bild till inferens-tjänsten och skriver ut resultatet.

    Fel (tjänsten nere, timeout) fångas och loggas bara — kameran ska fortsätta
    bevaka rörelse även om klassificeringen tillfälligt inte fungerar.
    """
    try:
        with open(image_path, "rb") as f:
            response = requests.post(url, files={"file": (image_path.name, f, "image/jpeg")}, timeout=10)
        response.raise_for_status()
        result = response.json()
        print(f"  → {result['species']} ({result['confidence']:.0%})")
    except requests.RequestException as e:
        print(f"  → inferens misslyckades: {e}")


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
    on_capture: Callable[[Path], None] | None = None,
) -> None:
    """
    Väntar på rörelse i frames och sparar en bild per upptäckt händelse.

    on_capture anropas efter varje sparad bild — production skickar den vidare till
    inferens-tjänsten (se __main__), testerna samlar bara sökvägarna i en lista.
    """
    prev_gray = None
    cooldown = 0
    recent_scores: list[float] = []  # för tuning-loggen nedan, en rad ungefär per minut.

    print("Väntar på rörelse (Ctrl+C för att avbryta)...")
    try:
        for gray, full in frames:
            if prev_gray is not None:
                score = motion_score(prev_gray, gray)
                recent_scores.append(score)

                if cooldown > 0:
                    cooldown -= 1
                elif score > MIN_CELL_FRACTION:
                    path = save_capture(full, save_dir)
                    print(f"Rörelse upptäckt — bild sparad: {path}")
                    if on_capture is not None:
                        on_capture(path)
                    cooldown = cooldown_frames

                # Skriver ut högsta rörelsepoängen senaste ~60 bilderna — ger en känsla i
                # journalctl för hur nära vinden ligger tröskeln, underlag för justering.
                if len(recent_scores) >= 60:
                    print(f"senaste minuten: max rörelsepoäng {max(recent_scores):.2f} (tröskel {MIN_CELL_FRACTION})")
                    recent_scores.clear()
            prev_gray = gray
    except KeyboardInterrupt:
        print("\nAvslutar.")


if __name__ == "__main__":
    run(PiCamera().frames(), on_capture=send_to_inference)
