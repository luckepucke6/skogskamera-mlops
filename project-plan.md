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
- [x] Koppla triggern till inferens-containern automatiskt — långlivad FastAPI-tjänst (uvicorn)
      istället för `docker run` per bild, se CLAUDE.md för designvalet

**Att hålla koll på:** `vcgencmd get_throttled` visade `0x50000` (historisk underspänning,
inte pågående) på Pi 3B+ efter belastningstestet — samma sorts flagga som Pi 4 hade innan
kabelbytet. Bevaka om den blir aktiv (`0x1`/`0x4`) under verklig drift.

### SKOG-011 — Koppla ihop noderna ✅
- [x] Skicka resultat (art, konfidens, tid, bild) från Pi 3B+ till Pi 4 — triggern POST:ar till
      `inference/app.py`, som loggar i bakgrunden så triggerloopen aldrig blockeras
- [x] Logga i MLflow — en run per detektion (`species`, `confidence`, `inference_ms`,
      bild-artefakt), verifierat via API
- [x] Exponera som Prometheus-metrics — `skogskamera_detections_total{species}`,
      `_inference_seconds`, `_last_confidence`, `_sink_errors_total{sink}`; target `edge-inference` UP
- [x] Bygg Grafana-dashboard — "Skogskamera" (5 paneler), provisionerad via
      `infra/monitoring/grafana-dashboards.yaml`
- [x] Koppla in Telegram-notis (ny bot, inte newscast-boten) — foto + bildtext bekräftat mottaget,
      takt-begränsad till 1/60s (FÖRENKLING, se CLAUDE.md)

**Problem som dök upp:** Grafana kraschade i loop (`Datasource provisioning error: data source
not found`) när ett fast `uid: prometheus` lades till på en datakälla som redan fanns med
auto-genererat uid sedan SKOG-008. Löst genom att radera PVC:n `grafana-data` (bara Grafanas
egna inställningar, ingen mätdata) och låta den provisionera om helt rent.

### SKOG-012 — Fullt integrationstest 🟡 (väntar på SKOG-011)
- [x] End-to-end-test: rörelse → bild → klassificering → logg → dashboard → notis — kört som en
      del av SKOG-011:s verifiering (samma kväll), inte som ett separat pass
- [ ] Testa CI/CD-flödet mot riktig hårdvara: kodändring → ny image → Pi 3B+ hämtar och kör den
- [x] Kör systemet en längre period (t.ex. ett dygn) och se att det är stabilt — triggern körs som
      systemd-tjänst (`skogskamera-trigger.service`, `Restart=always`), inferens-containern har
      `--restart unless-stopped`, båda överlever omstart/krasch utan aktiv SSH-session

**Resultat av dygnskörningen (13–15 sep):** ingen krasch i vare sig trigger eller inferens-tjänst.
99 detektioner, men ~94 var falska (vind i grenar/skuggor på gräset, se nedan) — bara ett fåtal
verkliga (personer). Två problem hittades och åtgärdades:
1. **Rörelsedetektering för känslig för vind:** bytte från "andel ändrade pixlar i hela bilden"
   till "mest ändrade rutans andel" (`motion_score` i `edge/camera_trigger.py`) + gaussisk
   blur. Verifierat offline mot alla 113 sparade bilder: alla 11 riktiga personpassager
   triggar fortfarande (0.55–1.00), vind-falsklarmen föll från ~30 till 3 (i den filtrerade
   analysen av bildpar med <15s mellanrum). De 3 kvarvarande orsakas av **direkt solljus i
   linsen** eftermiddagstid (linsflare är lika kompakt som ett djur) — ett optiskt problem,
   inte något tröskeljustering löser. Förslag: linshuv eller vinkla om kameran något.
2. **4 Telegram-notiser misslyckades** (`ReadTimeout`, `timeout=10`) — fotouppladdning tog
   ibland längre än så under belastning. Höjd till 30s. Lade även till loggrader vid lyckad
   sändning (`inference/app.py`) — tystnad vid fel var tidigare tvetydig (gick inte skilja
   "lyckades" från "kastades aldrig").
3. **Återkommande underspänning på Pi 3B+** (`throttled` aktiv, `dmesg` visar 10+ händelser/dygn)
   — öppen punkt, inte löst än. Samma symptombild som Pi 4 hade (SKOG-007/008). Nästa steg:
   kolla vilken kabel/adapter som används.

---

## Efter MVP (valfritt, inte kritiskt för portföljmålet)

- [ ] Fler modellklasser / förbättrad noggrannhet
- [x] Automatisk omstart vid krasch — klart, se SKOG-012
- [ ] Historik/statistik-vy i Grafana (t.ex. mest sedda arter per vecka)
- [ ] Streamlit-dashboard: bläddra captures + MLflow-resultat + rörelsepoäng över tid, för
      felsökning och tuning (användarens idé, 15/9) — separat från Grafana, mer interaktivt
- [ ] Skriva upp projektet (README med bilder/GIF av dashboard) för portföljen