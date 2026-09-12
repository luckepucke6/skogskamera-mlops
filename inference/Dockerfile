# Basimage: python:3.12-slim. Full "python:3.12" är onödigt stort; alpine
# (musl) saknar manylinux-wheels för numpy/pillow så pip måste kompilera
# själv. slim är samma familj (Debian) som Raspberry Pi OS.
FROM python:3.12-slim

WORKDIR /app

# Kopiera bara requirements.txt först — Docker cachar pip install-lagret
# så länge filen inte ändras, även om koden ändras.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# --no-cache-dir: cachen skulle bara ta onödig plats i imagen, ingen
# "nästa gång" finns i samma lager.

# Nu resten: modell, labels, testbilder och själva scriptet.
COPY models/ models/
COPY test-images/ test-images/
COPY test_model.py .

# ENTRYPOINT gör containern till ett kommando: `docker run <image> bild.jpg`
# motsvarar `python test_model.py bild.jpg`.
ENTRYPOINT ["python", "test_model.py"]
