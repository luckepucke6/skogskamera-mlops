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

### SKOG-005 — PIR→kamera-triggerlogik ✅ (ersatt i SKOG-010 — se not)
- [x] Skriv triggerlogik i Python med `gpiozero`
- [x] Testa mot en dummybild — `gpiozero.pins.mock.MockFactory` simulerar PIR-sensorn
- [x] Bilder sparas i `edge/captures/<UTC-tidsstämpel>.jpg`; anrop till inferens-containern byggs i SKOG-010
- **Ersatt:** lådan står bakom fönsterglas som blockerar PIR:ens IR-signal — bytt mot
  bildbaserad rörelsedetektering, se SKOG-010.

---

## Spår B: Väntar på SD-kort

### SKOG-006 — Flasha OS ✅
- [x] Flasha Pi 4 (SanDisk Extreme 64GB) — Raspberry Pi OS Lite (64-bit)
- [x] Flasha Pi 3B+ (SanDisk Ultra 64GB) — Raspberry Pi OS Lite (64-bit), `uname -m` → `aarch64` på båda
- [x] SSH-access uppsatt till båda — dedikerat nyckelpar (`~/.ssh/id_ed25519_skogskamera`), ingen lösenordsauth
- [x] Fyll i IP/hostname/SSH i `CLAUDE.md`-tabellen

### SKOG-007 — Kontrollera termik ✅ (delvis — se not)
- [x] `vcgencmd measure_temp` — 39.9°C (Pi 4) / 41.9°C (Pi 3B+) i viloläge, kör om under belastning (SKOG-008/010)
- [x] `vcgencmd get_throttled` — Pi 3B+ rent (`0x0`). Pi 4 visar `0x50000`: inte throttlad nu, men har hänt en gång
- [x] Beslut: ingen passiv kylfläns nu. Omvärderas om `throttled` visar pågående throttling under last
- **UPPFÖLJNING (2026-09-11 → löst 2026-09-12):** under-voltage inträffade under verklig last (k3s-uppstart),
  orsak en e-markerad USB-C-kabel. Löst med vanlig kabel, `throttled=0x0` sedan.

### SKOG-008 — Control plane på Pi 4 ✅
- [x] Installera k3s — `infra/k3s/setup-pi4.sh`, k3s v1.36.4+k3s1, cgroup v2/memory-fix
- [x] Installera/deploya MLflow — `infra/MLflow/mlflow.yaml`
- [x] Installera/deploya Prometheus — `infra/monitoring/prometheus.yaml`
- [x] Installera/deploya Grafana — `infra/monitoring/grafana.yaml`
- [x] Verifiera att alla tjänster svarar — `:5000/health`, `:9090/-/healthy`, `:3000/api/health` alla `HTTP 200`,
      end-to-end-test från Macen till MLflow bekräftat

**Problem som dök upp och hur de löstes:**
1. Brownout under last → löst med ny USB-C-kabel (se SKOG-007-uppföljningen).
2. Korrupt containerd-cache efter brownout-krascherna → raderade `/var/lib/rancher/k3s/agent/containerd`
   (bara image-cache, inte serverdata) och lät allt laddas om.
3. MLflow 3.x OOMKilled vid uppstart (minnestopp ~1.6 GB) → höjde `limits.memory` till 2Gi.
4. MLflow 3.x avvisade requests via hostnamn (DNS-rebinding-skydd) → satte
   `MLFLOW_SERVER_ALLOWED_HOSTS=*`, flaggad förenkling i CLAUDE.md.

**Att hålla koll på framöver:** minnesbudgeten är trång (~3Gi `limits.memory` av 3.8 GB totalt). Fungerar idag,
blir trängre när SKOG-011 lägger till riktigt dataflöde.

### SKOG-009 — Fysisk montering Pi 3B+ ✅
- [x] Montera InnoMaker OV5647-kameran
- [x] Koppla PIR HC-SR501 i GPIO (ersatt i SKOG-010 — lådan står bakom fönsterglas, PIR ser inte IR genom glas)
- [x] Verifiera att kameran kan ta en bild via kommandorad — `rpicam-still`, bild bekräftad skarp
- [x] Verifiera att PIR-sensorn triggar en signal du kan läsa av — `pinctrl get 4`, lo→hi vid rörelse bekräftat

### SKOG-010 — Deploya edge-koden på Pi 3B+ ✅
- [x] Skriv om triggern till bildjämförelse (`picamera2`) — PIR fungerar inte bakom fönsterglas
- [x] Verifiera riktig rörelsedetektering vid fönstret — 8 bilder sparade, verklig rörelse bekräftad visuellt
- [x] Flytta över triggerlogik + inferens-container till Pi 3B+ — Docker installerad (inte k3s, se CLAUDE.md),
      `ghcr.io/luckepucke6/skogskamera-mlops/inference:latest` hämtad och körd
- [x] Kör en riktig lokal inferens (inte dummybild) på Pi 3B+ — klassade en riktig bild från kameran
- [x] Mät prestanda — se CLAUDE.md för siffror
- [ ] Koppla triggern till inferens-containern automatiskt (designval: `docker run` per bild eller
      långlivad tjänst — hör ihop med SKOG-011:s behov av strukturerade resultat till MLflow)

**Att hålla koll på:** `vcgencmd get_throttled` visade `0x50000` (historisk underspänning,
inte pågående) på Pi 3B+ efter belastningstestet — samma sorts flagga som Pi 4 hade innan
kabelbytet. Bevaka om den blir aktiv (`0x1`/`0x4`) under verklig drift.

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