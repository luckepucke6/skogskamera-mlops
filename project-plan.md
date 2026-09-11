# Projektplan – Skogskamera MLOps

Din egen tasklista. Bocka av `[ ]` → `[x]` allteftersom. Ordningen inom varje spår är tänkt att
följas, men spåren emellan (Mac-spåret vs Pi-spåret) är oberoende — du kan börja med båda om du
vill, men rekommenderat är att köra klart Mac-spåret först.

Status-nyckel: 🟢 kan börja nu · 🟡 väntar på beroende · ⚪ inte påbörjad

---

## Spår A: Kan göras nu (bara Mac, ingen Pi krävs)

### SKOG-001 — Grundstruktur 🟢
- [x] Mappstruktur skapad (`.github/workflows`, `edge`, `inference`, `infra`, `MLflow`)
- [x] Git init + `.gitignore`
- [x] README.md i roten
- [x] `CLAUDE.md` på plats i repo-roten

### SKOG-002 — Modell mot bilder 🟢
- [x] Välj en färdig TFLite- eller ONNX-modell (t.ex. MobileNet SSD, eller sök efter en
      djur/fågel-specifik klassificerare)
- [x] Kör modellen mot ett gäng testbilder lokalt på Mac
- [x] Notera prestanda/noggrannhet-avvägning — kommer behövas senare för kvantiseringsvalet
- [x] Spara ner testbilder du använt (till `inference/test-images/` eller liknande)

### SKOG-003 — Inferens-container ✅
- [x] Dockerfile i `inference/` som paketerar modell + inferenskod
- [x] Bygg och kör lokalt i Docker Desktop
- [x] Verifiera att containern klassar en bild korrekt end-to-end (in: bild, ut: art + konfidens)
- [x] Håll containern så liten som möjligt (tänk redan nu på Pi 3B+:ans resurser)

### SKOG-004 — CI/CD-workflow ✅
- [x] GitHub Actions-workflow: bygg containern från SKOG-003
- [x] Pusha till ett registry (t.ex. GHCR)
- [x] Testa med en dummy-commit att pipelinen faktiskt triggas och lyckas
      (behövdes inte separat — själva workflow-commiten triggade första körningen)

### SKOG-005 — PIR→kamera-triggerlogik ✅
- [x] Skriv triggerlogik i Python med `gpiozero`
- [x] Testa logiken mot en dummybild (ingen riktig GPIO/kamera än) — `gpiozero.pins.mock.MockFactory`
      simulerar PIR-sensorn, `capture_image()` kopierar en testbild från `inference/test-images/`
- [x] Definiera var bilden ska hamna och hur den skickas vidare till inferens-steget — bilder
      sparas i `edge/captures/<UTC-tidsstämpel>.jpg`; själva anropet till inferens-containern
      byggs medvetet inte förrän SKOG-010 (se motivering i `edge/camera_trigger.py`)

---

## Spår B: Väntar på SD-kort

### SKOG-006 — Flasha OS ✅
- [x] Flasha Pi 4 (SanDisk Extreme 64GB) — Raspberry Pi OS Lite (64-bit)
- [x] Flasha Pi 3B+ (SanDisk Ultra 64GB) — Raspberry Pi OS Lite (64-bit), verifierat `uname -m` →
      `aarch64` på båda (OS-kravet i CLAUDE.md uppfyllt)
- [x] Grundläggande SSH-access uppsatt till båda — dedikerat nyckelpar (`~/.ssh/id_ed25519_skogskamera`),
      ingen lösenordsauth
- [x] Fyll i IP/hostname/SSH i `CLAUDE.md`-tabellen

### SKOG-007 — Kontrollera termik ✅ (delvis — se not)
- [x] `vcgencmd measure_temp` på båda — 39.9°C (Pi 4) / 41.9°C (Pi 3B+), men bara i viloläge
      direkt efter boot, inte under belastning. Kör om när Pi 4 faktiskt kör k3s+MLflow+
      Prometheus+Grafana (SKOG-008) och när Pi 3B+ kör riktig inferens (SKOG-010).
- [x] `vcgencmd get_throttled` — Pi 3B+ helt rent (`0x0`). Pi 4 visar `0x50000`: INTE throttlad
      just nu, men under-voltage/throttling har inträffat en gång sedan boot (troligen
      strömkällan/kabeln vid första uppstart) — se detaljer i CLAUDE.md-tabellen, håll koll
      igen under verklig last.
- [x] Beslut: ingen passiv kylfläns köps in nu — inget aktivt throttlar. Omvärderas om
      `throttled` visar bit 0/2 (pågående) under verklig last senare.

### SKOG-008 — Control plane på Pi 4 🟡 (väntar på SKOG-006)
- [ ] Installera k3s
- [ ] Installera/deploya MLflow
- [ ] Installera/deploya Prometheus
- [ ] Installera/deploya Grafana
- [ ] Verifiera att alla tjänster svarar (basic health check, inget dataflöde än)

### SKOG-009 — Fysisk montering Pi 3B+ 🟡 (väntar på SKOG-006)
- [ ] Montera InnoMaker OV5647-kameran
- [ ] Koppla PIR HC-SR501 i GPIO
- [ ] Verifiera att kameran kan ta en bild via kommandorad
- [ ] Verifiera att PIR-sensorn triggar en signal du kan läsa av

### SKOG-010 — Deploya edge-koden på Pi 3B+ 🟡 (väntar på SKOG-005 + SKOG-009)
- [ ] Flytta över triggerlogik + inferens-container till Pi 3B+
- [ ] Kör en riktig lokal inferens (inte dummybild) på Pi 3B+
- [ ] Mät prestanda (hur lång tid tar en inferens på riktig hårdvara?)

### SKOG-011 — Koppla ihop noderna 🟡 (väntar på SKOG-008 + SKOG-010)
- [ ] Skicka resultat (art, konfidens, tid, bild) från Pi 3B+ till Pi 4
- [ ] Logga i MLflow
- [ ] Exponera som Prometheus-metrics
- [ ] Bygg Grafana-dashboard
- [ ] Koppla in Telegram-notis (återanvänd befintlig bot-kod)

### SKOG-012 — Fullt integrationstest 🟡 (väntar på SKOG-011)
- [ ] End-to-end-test: rörelse → bild → klassificering → logg → dashboard → notis
- [ ] Testa CI/CD-flödet mot riktig hårdvara: kodändring → ny image → Pi 3B+ hämtar och kör den
- [ ] Kör systemet en längre period (t.ex. ett dygn) och se att det är stabilt

---

## Efter MVP (valfritt, inte kritiskt för portföljmålet)

- [ ] Fler modellklasser / förbättrad noggrannhet
- [ ] Automatisk omstart vid krasch (systemd eller k3s-nivå)
- [ ] Historik/statistik-vy i Grafana (t.ex. mest sedda arter per vecka)
- [ ] Skriva upp projektet (README med bilder/GIF av dashboard) för portföljen