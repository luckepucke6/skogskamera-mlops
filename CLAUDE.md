# CLAUDE.md

Kontext och konventioner för Claude Code i det här repot. Läs detta innan du föreslår eller skriver kod.

## Projektet i korthet

Mini-MLOps-plattform som upptäcker och klassificerar djur/fåglar i skogen utanför ett fönster.
Portföljprojekt för en MLOps Engineer-utbildning (YH). Syftet är att visa upp ett komplett
produktionsliknande ML-flöde: containerisering, orkestrering, model registry, monitoring, CI/CD.
Inte ett hobby-scraping-projekt — varje del ska motsvara vad en riktig MLOps-pipeline gör, fast
nedskalad till Raspberry Pi-hårdvara.

## Hårdvara och noder

| Nod | Hårdvara | Roll | Hostname | IP | SSH |
|---|---|---|---|---|---|
| Pi 4 | Raspberry Pi 4 Model B (2018) | Control plane | `skog-pi4` | 192.168.1.86 (DHCP, ej reserverad) | `ssh -i ~/.ssh/id_ed25519_skogskamera skog@skog-pi4.local` |
| Pi 3B+ | Raspberry Pi 3 Model B+ (2017) | Edge-nod | `skog-pi3` | 192.168.1.88 (DHCP, ej reserverad) | `ssh -i ~/.ssh/id_ed25519_skogskamera skog@skog-pi3.local` |

SD-kort: SanDisk Extreme 64GB A2/U3 → Pi 4. SanDisk Ultra 64GB A1 → Pi 3B+. Båda flashade med
Raspberry Pi OS Lite (64-bit, Debian trixie) via Raspberry Pi Imager, headless (SSH-nyckel,
ingen lösenordsauth). Verifierat `uname -m` → `aarch64` på båda.

IP:erna ovan är nu **reserverade i routern** (DHCP-reservation på MAC-adress) — krävdes för
SKOG-011, eftersom varken Docker-containern på Pi 3B+ eller Prometheus-podden i k3s kan slå upp
`.local`-mDNS-namn. All config mellan noderna (Prometheus scrape-mål, `MLFLOW_TRACKING_URI`)
använder därför IP, inte hostnamn. `.local` funkar fortfarande fint för SSH/kubectl från Macen.

Ingen aktiv kylning — `vcgencmd measure_temp`/`get_throttled` har inte visat behov av kylfläns.

**Strömförsörjning — VIKTIGT (SKOG-007/008):** Pi 4 startade om spontant under-voltage när k3s
+ containerd drog igång (`throttled=0x50005`). Orsak: en e-markerad USB-C-kabel — Pi 4 har en
känd CC-pin-hårdvarubugg som gör den känslig för sådana kablar. Löst med en vanlig,
icke-e-markerad kabel (`throttled=0x0` sedan). **Vid underspänning igen: misstänk kabeln,
inte adaptern, först.**

## Arkitektur

- **Pi 4 (control plane):** k3s, MLflow (model registry), Prometheus + Grafana (monitoring)
- **Pi 3B+ (edge-nod):** InnoMaker OV5647 CSI-kamera, lokal inferens med kvantiserad TFLite/ONNX-
  modell. Rörelse upptäcks genom bildjämförelse (picamera2), inte PIR-sensor — lådan står bakom
  fönsterglas som blockerar PIR:ens IR-signal (HC-SR501 testades och fungerar, se SKOG-009, men
  ersattes i SKOG-010).

**OS-krav (viktigt vid SKOG-006):** Pi 3B+ måste flashas med **64-bitars** Raspberry Pi OS.
`ai-edge-litert` (TFLite-interpretern vi använder, se `inference/`) har inga wheels för
32-bitars ARM — med 32-bitars OS går inferens-containern inte ens att installera. Verifierat
via PyPI-metadata för `ai-edge-litert==2.2.0`.

## Control plane på Pi 4 (SKOG-008)

k3s (v1.36.4+k3s1) + MLflow + Prometheus + Grafana kör och svarar. Manifest i `infra/`
(se Mappstruktur). Inget dataflöde från edge-noden än — det är SKOG-011.

- **kubectl från Macen:** `export KUBECONFIG=~/.kube/skogskamera.yaml` (separat fil, inte
  merge:ad i `~/.kube/config`). Pekar på IPv4 direkt (`https://192.168.1.86:6443`) med
  `tls-server-name: skog-pi4.local`, INTE `https://skog-pi4.local:6443` — mDNS ger både A- och
  AAAA-post, och Go:s HTTP-klient väljer ibland IPv6, som timeoutar. Blir kubectl
  långsamt/instabilt igen: misstänk detta först.
- **Tjänster:** `http://skog-pi4.local:5000` (MLflow), `:9090` (Prometheus), `:3000` (Grafana,
  `admin` + lösenord satt via `kubectl create secret generic grafana-admin -n monitoring
  --from-literal=admin-password=...` — står INTE i git, fråga i chatten om det behövs igen).
- **Ingen autentisering på MLflow/Prometheus**, **`MLFLOW_SERVER_ALLOWED_HOSTS=*`** i
  `infra/MLflow/mlflow.yaml`: MLflow 3.x har ett DNS-rebinding-skydd som annars avvisar
  requests via hostnamn. Medveten förenkling för ett hemmanätverk, se kommentar i manifestet.
- **MLflow behöver minst 2Gi minnesgräns** — mindre (1Gi, 1536Mi) gav OOMKilled vid uppstart
  (FastAPI/uvicorn-import + SQLite-migrering toppar ~1.6 GB, sjunker sedan kraftigt).
- Konstiga containerfel efter brownout/oplanerad omstart → misstänk korrupt containerd-cache,
  inte konfigurationen. Fix: stoppa k3s, radera `/var/lib/rancher/k3s/agent/containerd` (bara
  image-cache, INTE serverdata i `/var/lib/rancher/k3s/server`), starta k3s igen.
- **Minnesbudget är trång:** `limits.memory` summerar till ~3Gi (MLflow 2Gi + Prometheus
  512Mi + Grafana 512Mi) på en Pi 4 med 3.8 GB totalt. Fungerar idag, men blir trängre när
  SKOG-011 lägger till riktigt dataflöde — håll koll med `kubectl top pods -A`.

## Edge-nod Pi 3B+ (SKOG-010/011)

- **Docker, inte k3s** — en Pi 3B+ med 905 MB RAM kör bara en container (inferens); k3s-agenten
  hade själv ätit ~300 MB i onödan.
- **Långlivad FastAPI-tjänst (`inference/app.py`), inte `docker run` per bild** — modellen laddas
  en gång vid start istället för per anrop. Gick från ~2,5 s totalt per klassificering till
  ~140 ms ren inferens. Bonus: Prometheus behöver ändå en HTTP-endpoint att skrapa.
- Start: `docker run -d --name inference --restart unless-stopped -p 8000:8000
  --env-file ~/skogskamera/.env ghcr.io/luckepucke6/skogskamera-mlops/inference:latest`.
  `.env` (mall: `inference/.env.example`, riktiga värden bara på Pi:n, aldrig i git):
  `MLFLOW_TRACKING_URI`, `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`, `TELEGRAM_MIN_INTERVAL_S`.
  `--restart unless-stopped` = Docker startar om tjänsten själv vid krasch/omstart.
- Endpoints: `GET /health`, `POST /classify` (multipart bild), `GET /metrics` (Prometheus).
  Triggern (`edge/camera_trigger.py`) POST:ar dit efter varje sparad bild; fel (tjänsten nere)
  loggas men stoppar aldrig rörelsebevakningen.
- **Ny Telegram-bot** skapad för det här projektet (inte newscast-boten) — samma
  `requests`-mot-Bot-API-mönster återanvänt, men egen token/chat-id.
- MLflow-loggning och Telegram-notis körs som `BackgroundTasks` — svaret till triggern skickas
  innan de körs klart, så ett långsamt/nere MLflow aldrig fördröjer nästa bild.

## Dataflöde

1. Kameran upptäcker rörelse genom att jämföra bilder (`edge/camera_trigger.py`)
2. En bild i full upplösning sparas och POST:as till inferens-tjänsten (`inference/app.py`)
3. TFLite-modellen klassar bilden, svarar direkt med art + konfidens
4. I bakgrunden: resultatet loggas som en MLflow-run på Pi 4 (art, konfidens, tid, bild-artefakt)
   och exponeras som Prometheus-metrics på tjänstens `/metrics`
5. Grafana-dashboarden "Skogskamera" visar datan, Telegram-notis skickas (takt-begränsad, se
   Edge-nod-avsnittet)

## CI/CD (separat flöde, inte samma som dataflödet ovan)

Kodändring → GitHub Actions bygger container → pushar till registry → Pi 3B+ hämtar och kör ny
modellversion. Håll isär detta flöde från inferens-dataflödet i kod och i diskussion.

## Mappstruktur

```
.github/workflows/          CI/CD-pipelines
edge/                       kamera-triggerlogik (bildjämförelse), körs på Pi 3B+
inference/                  modell + app.py (FastAPI-tjänst) + Dockerfile
infra/k3s/                  setup-pi4.sh — cgroup-fix + k3s-installation
infra/MLflow/               mlflow.yaml (k3s-manifest)
infra/monitoring/           prometheus.yaml, grafana.yaml, grafana-dashboards.yaml (k3s-manifest)
```

(Notera versaliseringen `MLflow/` — konsekvent skiftläge, matchar den mapp SKOG-001 redan
skapade. macOS eget filsystem är skiftlägesokänsligt så `mlflow/` och `MLflow/` är SAMMA
katalog där — skapa aldrig båda, det ger förvirring så fort någon klonar på Linux.)

## Byggordning — respektera denna, hoppa inte i ordning

**Kan göras nu (bara Mac, ingen Pi krävs):**
1. Testa en färdig TFLite/ONNX-modell mot bilder
2. Bygg och testa inferens-containern i Docker Desktop
3. GitHub Actions-workflow (bygg + push till registry)
4. Kamera-triggerlogik i Python (bildjämförelse, `numpy`/`Pillow`), testad mot testbilder

**Väntar på SD-kort:**
- Flasha OS på båda Pi:sarna
- k3s + MLflow + Prometheus + Grafana på Pi 4
- Fysisk montering av kamera på Pi 3B+ (PIR testades men ersattes, se Arkitektur)
- Fullt integrationstest end-to-end

Om en uppgift tillhör steg 2 (väntar på SD-kort) och SD-korten inte är flashade än — säg det,
föreslå inte att simulera eller hoppa över.

## Konventioner

- Python för all applikationskod (edge-logik, inferens)
- En sak per session/uppgift — bygg inte flera pipeline-steg i samma svep
- Committa i små, fungerande steg
- Håll `inference/` och `edge/` oberoende av varandra där det går — Pi 3B+ har begränsade resurser,
  onödiga beroenden mellan moduler gör edge-noden tyngre än den behöver vara

## Kodstil: pedagogisk, inte bara produktionsmässig

Lärprojekt — användaren är inte erfaren utvecklare och vill förstå koden, inte bara ha den
fungerande. **Kommentarer ska vara korta: 1-3 rader, inte långa.**

- Kommentera **varför**, inte bara vad — särskilt MLOps-koncept (t.ex. varför kvantisering
  behövs, varför model registry skiljer sig från att spara en fil, vad en k3s-manifest-nyckel gör).
- Förklara okända bibliotek/mönster kort (1-3 rader) första gången de dyker upp i koden
  (t.ex. `picamera2`, MLflow:s `log_metric` vs `log_artifact`, Docker multi-stage builds).
- Vid icke-triviala designval: motivera kort i svaret också (inte bara i koden) varför du valde
  en lösning framför en annan.
- Flagga förenklingar mot en riktig produktionsmiljö (t.ex. ingen autentisering, hårdkodade
  trösklar) med en kort kommentar, så det syns att det är medvetet och inte en miss.

## Tidigare projekt att återanvända från

- **ELLA** (RAG-chatbot): erfarenhet av Docker/FastAPI/MLflow finns redan därifrån
- **Telegram-bot-bridge:** koden finns kvar, återanvänd för notiser — bygg inte om från scratch

## Budget

Ny hårdvara hölls medvetet nere (~770 kr totalt). Prioritera enkla, robusta lösningar framför
överkomplicerade — det gäller även mjukvaruval (t.ex. k3s istället för full Kubernetes, av samma skäl).