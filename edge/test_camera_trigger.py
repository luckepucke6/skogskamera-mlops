"""
Testar trigger-logiken utan riktig GPIO/kamera, körs på Mac.
MockFactory ger låtsas-GPIO-pinnar (drive_high/drive_low) istället för hårdvara.
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
    Byter till MockFactory per test. Utan den kraschar gpiozero direkt på
    Mac, den försöker prata med riktig GPIO-hårdvara som inte finns.
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
    Simulerar rörelse (pinnen driver högt) och verifierar att vår
    capture-funktion anropas — dvs att VI kopplat ihop callbacken rätt.
    """
    calls = []

    def fake_capture() -> Path:
        calls.append(True)
        return Path("dummy.jpg")

    # VIKTIGT: spara returvärdet. gpiozero håller bara en weakref till sensorn,
    # så utan en egen referens skräpsamlas den direkt och bakgrundstråden dör.
    pir = build_sensor(PIR_GPIO_PIN, fake_capture)

    pin = Device.pin_factory.pin(PIR_GPIO_PIN)

    # MotionSensor pollar pinnen i en bakgrundstråd, och dess FÖRSTA avläsning
    # bara sätter utgångsläge utan callback. Vi väntar in den innan vi driver
    # pinnen hög, annars blir det höga värdet själva utgångsläget istället för en förändring.
    time.sleep(0.15)

    pin.drive_high()  # simulerar att HC-SR501 känner rörelse
    time.sleep(0.3)

    assert calls == [True]
    assert pir.is_active

    pin.drive_low()
