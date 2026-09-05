# Testbilder

Lägg testbilder i den här mappen. `test_model.py` letar inte efter dem
automatiskt — du anger sökvägen som argument:

```
python test_model.py test-images/ditt-filnamn.jpg
```

## Format och storlek

- **Format:** JPG eller PNG duger båda — scriptet konverterar alltid till
  RGB innan klassificering.
- **Storlek:** ingen exakt storlek krävs. Scriptet läser modellens
  förväntade upplösning (224×224 för den nuvarande MobileNetV2-modellen)
  och skalar om bilden automatiskt.
- **Men:** undvik väldigt små bilder (t.ex. < 224×224). Att skala UPP en
  liten bild lägger bara till suddiga pixlar, det tillför ingen ny
  information — modellen får i praktiken sämre indata än om bilden redan
  var tillräckligt stor från början. En vanlig mobilbild (flera hundra
  pixlar brett) är mer än tillräckligt.
- **Motiv:** eftersom nuvarande modell är en generisk ImageNet-klassificerare
  (se kommentar i `test_model.py`), testa gärna med bilder på vardagsobjekt
  eller djur som faktiskt finns i ImageNet (t.ex. hund, katt, räv, hjort)
  för att verifiera att pipelinen fungerar — förvänta dig inte träffsäker
  klassificering av t.ex. specifika svenska fågelarter än.

Bilderna committas till repot (se `.gitignore` — mappen är inte
undantagen), så att SKOG-002 blir reproducerbart för andra som klonar
repot. Om mappen växer sig stor senare kan vi undanta den i `.gitignore`.
