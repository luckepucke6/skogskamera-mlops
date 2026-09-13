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
COPY test_model.py app.py ./

# MLflow-klienten (gitpython) letar efter en git-binär för att stämpla runs med commit-SHA.
# Den finns inte i imagen — utan den här raden bara varnar den, men tyst är trevligare.
ENV GIT_PYTHON_REFRESH=quiet

EXPOSE 8000

# Långlivad tjänst istället för `docker run <image> bild.jpg` (se app.py för varför) —
# därför uvicorn som ENTRYPOINT, inte python test_model.py.
ENTRYPOINT ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8000"]
