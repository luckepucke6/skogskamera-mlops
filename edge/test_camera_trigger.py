"""
edge/test_camera_trigger.py — testar trigger-logiken UTAN riktig GPIO/kamera.

Körs på Mac, ingen Pi krävs. Två saker testas separat, i tur och ordning
efter hur pipelinen faktiskt ser ut:

1. capture_image() — sparar den (simulerade) kameran faktiskt en bildfil?
2. build_sensor() — reagerar PIR-kopplingen på ett rörelse-event genom att
   anropa capture-funktionen?

gpiozero har ett inbyggt sätt att testa PIR/LED/knapp-kod utan hårdvara:
MockFactory. Istället för att prata med riktiga GPIO-pinnar via RPi.GPIO/
lgpio (vilket kräver att man kör på en Pi) skapar den låtsas-pinnar man kan
styra manuellt från testkoden (`pin.drive_high()` / `pin.drive_low()`) —
ungefär som att fysiskt koppla PIR-sensorns utgång till en spänning.
"""

import time
from pathlib import Path

import pytest
from gpiozero import Device
from gpiozero.pins.mock import MockFactory

from camera_trigger import PIR_GPIO_PIN, build_sensor, capture_image


@pytest.fixture(autouse=True)
def mock_gpio():
    """
    Byter ut gpiozero:s pin factory mot MockFactory för varje test, och
    städar upp igen efteråt. Utan den här bytas skulle gpiozero försöka
    prata med riktig GPIO-hårdvara vid import/körning — vilket kraschar
    direkt på en Mac (ingen sådan hårdvara finns).
    """
    Device.pin_factory = MockFactory()
    yield
    Device.pin_factory.reset()


def test_capture_image_saves_a_jpg_file(tmp_path):
    dest = capture_image(save_dir=tmp_path)

    assert dest.exists()
    assert dest.suffix == ".jpg"
    assert dest.parent == tmp_path


def test_motion_event_triggers_capture():
    """
    Simulerar att PIR-sensorn känner rörelse (låtsas-pinnen driva högt) och
    verifierar att vår capture-funktion faktiskt anropas som callback —
    inte att gpiozero "fungerar" i sig, utan att VI kopplat ihop den rätt.
    """
    calls = []

    def fake_capture() -> Path:
        calls.append(True)
        return Path("dummy.jpg")

    # VIKTIGT: spara returvärdet. gpiozero:s bakgrundstråd (som pollar
    # pinnen och triggar callbacks) håller bara en `weakref` till sensor-
    # objektet — ett medvetet designval så att tråden dör automatiskt om
    # sensorn skräpsamlas. Om vi inte behåller en referens här skräpsamlas
    # objektet direkt när build_sensor() returnerar (refcount går till 0),
    # och bakgrundstråden dör innan den hinner läsa av pinnen en enda gång.
    pir = build_sensor(PIR_GPIO_PIN, fake_capture)

    pin = Device.pin_factory.pin(PIR_GPIO_PIN)

    # MotionSensor läser inte av pinnen direkt vid förändring — den är en
    # SmoothedInputDevice som pollar pinnen i en bakgrundstråd (default
    # sample_rate=10/s, dvs. var 0.1:e sekund). Dess ALLRA FÖRSTA avläsning
    # sätter bara ett utgångsläge (ingen callback triggas då, oavsett
    # värde) — det är först vid en FÖRÄNDRING mot det utgångsläget som
    # when_motion triggas. Vi väntar därför in den första avläsningen
    # (etablerar "ingen rörelse") INNAN vi simulerar rörelse, annars
    # riskerar vi att låtsas-pinnens redan-höga värde blir utgångsläget
    # istället för en övergång.
    time.sleep(0.15)

    pin.drive_high()  # simulerar att HC-SR501 känner rörelse
    time.sleep(0.3)

    assert calls == [True]
    assert pir.is_active

    pin.drive_low()
