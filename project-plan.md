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

### SKOG-005 — PIR→kamera-triggerlogik 🟢 (oberoende av övriga i spår A)
- [ ] Skriv triggerlogik i Python med `gpiozero`
- [ ] Testa logiken mot en dummybild (ingen riktig GPIO/kamera än)
- [ ] Definiera var bilden ska hamna och hur den skickas vidare till inferens-steget

---

## Spår B: Väntar på SD-kort

### SKOG-006 — Flasha OS 🟡 (väntar på att SD-korten införskaffas)
- [ ] Flasha Pi 4 (SanDisk Extreme 64GB)
- [ ] Flasha Pi 3B+ (SanDisk Ultra 64GB) — **måste vara 64-bitars Raspberry Pi OS**, se
      OS-kravet i `CLAUDE.md`: `ai-edge-litert` saknar wheels för 32-bitars ARM
- [ ] Grundläggande SSH-access uppsatt till båda
- [ ] Fyll i IP/hostname/SSH i `CLAUDE.md`-tabellen

### SKOG-007 — Kontrollera termik 🟡 (väntar på SKOG-006)
- [ ] `vcgencmd measure_temp` på båda under lätt belastning
- [ ] `vcgencmd get_throttled` — kolla om throttling sker
- [ ] Besluta om passiv kylfläns behövs (köp bara om det faktiskt throttlar)

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