# SKOG-003 — Inferens-container.
#
# Basimage: python:3.12-slim, inte python:3.12 eller python:3.12-alpine.
# - Fulla "python:3.12" drar in kompilatorer, dokumentation och verktyg vi
#   aldrig behöver för att bara köra en färdigtränad modell — onödigt stort.
# - Alpine (musl libc) är ofta ännu mindre, men numpy/pillow saknar
#   färdigbyggda ("manylinux") wheels för musl. Med alpine skulle pip tvingas
#   kompilera dem från källkod vid varje bygge, vilket är långsamt och kräver
#   extra byggverktyg i imagen — det äter upp precis den storleksvinst man
#   var ute efter. "slim" (Debian + glibc) är den vanliga kompromissen för
#   Python + vetenskapliga paket, och är samma familj vi kommer använda på
#   Pi 3B+ (Raspberry Pi OS är också Debian-baserat).
FROM python:3.12-slim

WORKDIR /app

# Kopiera BARA requirements.txt först, inte resten av koden än. Docker
# cachar varje instruktion som ett eget lager. Så länge requirements.txt
# inte ändras återanvänds "pip install"-lagret vid nästa bygge, även om vi
# just ändrat test_model.py. Ändrar vi ordningen (kod före requirements)
# skulle varenda kodändring tvinga fram en ny, långsam paketinstallation.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# --no-cache-dir ovan: pip sparar normalt nedladdade paket i en cache för
# att slippa hämta om dem nästa gång. I en container finns aldrig en
# "nästa gång" på samma lager — cachen skulle bara ligga kvar och ta plats
# i den färdiga imagen utan att någonsin användas.

# Nu resten: modell, labels, testbilder och själva scriptet.
COPY models/ models/
COPY test-images/ test-images/
COPY test_model.py .

# ENTRYPOINT (inte CMD) gör containern till ett "kommando" i sig — du kör
# `docker run <image> test-images/2a.jpg` ungefär som `python test_model.py
# test-images/2a.jpg` lokalt. Bildsökvägen skickas med som argument vid
# `docker run`, den bakas inte in i imagen.
ENTRYPOINT ["python", "test_model.py"]
