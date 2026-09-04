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
| Pi 4 | Raspberry Pi 4 Model B (2018) | Control plane | TBD | TBD | TBD |
| Pi 3B+ | Raspberry Pi 3 Model B+ (2017) | Edge-nod | TBD | TBD | TBD |

SD-kort: SanDisk Extreme 64GB A2/U3 → Pi 4. SanDisk Ultra 64GB A1 → Pi 3B+.
Ingen aktiv kylning inledningsvis — kontrollera `vcgencmd measure_temp` och `vcgencmd get_throttled`
innan ev. passiv kylfläns köps in.

**OBS:** Rader ovan är platshållare tills SD-korten är flashade. Föreslå inga SSH-kommandon mot
riktiga IP:er förrän den här tabellen är ifylld — fråga istället.

## Arkitektur

- **Pi 4 (control plane):** k3s, MLflow (model registry), Prometheus + Grafana (monitoring)
- **Pi 3B+ (edge-nod):** InnoMaker OV5647 CSI-kamera + PIR-sensor HC-SR501 (direkt i GPIO, ingen
  Pico W/MQTT), lokal inferens med kvantiserad TFLite/ONNX-modell

## Dataflöde

1. PIR-sensor känner rörelse
2. Kameran tar en stillbild
3. TFLite-modellen på Pi 3B+ klassar innehållet
4. Resultat (art, konfidens, tid, bild) skickas till Pi 4 → loggas i MLflow, exponeras som
   Prometheus-metrics
5. Grafana-dashboard uppdateras, Telegram-notis skickas (återanvänd befintlig bot-kod, bygg inte om)

## CI/CD (separat flöde, inte samma som dataflödet ovan)

Kodändring → GitHub Actions bygger container → pushar till registry → Pi 3B+ hämtar och kör ny
modellversion. Håll isär detta flöde från inferens-dataflödet i kod och i diskussion.

## Mappstruktur

```
.github/workflows/   CI/CD-pipelines
edge/                PIR + kamera-triggerlogik, körs på Pi 3B+
inference/            modell + Dockerfile för inferenscontainer
infra/                k3s-manifest, Prometheus/Grafana-config
MLflow/               MLflow-relaterad config/setup
```

## Byggordning — respektera denna, hoppa inte i ordning

**Kan göras nu (bara Mac, ingen Pi krävs):**
1. Testa en färdig TFLite/ONNX-modell mot bilder
2. Bygg och testa inferens-containern i Docker Desktop
3. GitHub Actions-workflow (bygg + push till registry)
4. PIR→kamera-triggerlogik i Python (`gpiozero`), testad mot en dummybild — ingen riktig GPIO än

**Väntar på SD-kort:**
- Flasha OS på båda Pi:sarna
- k3s + MLflow + Prometheus + Grafana på Pi 4
- Fysisk montering av kamera + PIR på Pi 3B+
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

Det här projektet drivs för att lära sig, inte bara för att bli klart — användaren är inte
erfaren utvecklare och vill förstå koden medan den skrivs, inte bara ha den fungerande.

- Kommentera **varför**, inte bara vad — särskilt vid MLOps-specifika koncept
  (t.ex. varför kvantisering behövs, varför model registry skiljer sig från att bara spara en
  fil, varför Prometheus-metrics är strukturerade som de är, vad en k3s-manifest-nyckel gör).
- Förklara okända bibliotek/mönster första gången de dyker upp i koden (t.ex. `gpiozero`,
  MLflow:s `log_metric` vs `log_artifact`, Docker multi-stage builds) — en rad eller två räcker,
  behöver inte vara en föreläsning.
- Vid icke-triviala designval: säg gärna kort i svaret (inte bara i koden) *varför* du valde en
  lösning framför en annan, särskilt om det finns ett enklare men sämre alternativ.
- Prioritera läsbarhet över kompakthet — hellre några extra rader som är tydliga än en tät
  one-liner, även om det är "produktionsstandard" att skriva kortare.
- Om något är en förenkling jämfört med hur det skulle göras i en riktig produktionsmiljö
  (t.ex. ingen autentisering mellan noderna, hårdkodade trösklar) — flagga det i en kommentar,
  så användaren vet vad som är en medveten avvägning och inte en miss.

## Tidigare projekt att återanvända från

- **ELLA** (RAG-chatbot): erfarenhet av Docker/FastAPI/MLflow finns redan därifrån
- **Telegram-bot-bridge:** koden finns kvar, återanvänd för notiser — bygg inte om från scratch

## Budget

Ny hårdvara hölls medvetet nere (~770 kr totalt). Prioritera enkla, robusta lösningar framför
överkomplicerade — det gäller även mjukvaruval (t.ex. k3s istället för full Kubernetes, av samma skäl).