"""Keep the two Lovelace card copies identical."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RS485 = (
    ROOT
    / "custom_components"
    / "pentair_rs485"
    / "www"
    / "pentair-pump-display-card.js"
)
DISPLAY = (
    ROOT
    / "custom_components"
    / "pentair_pump_display"
    / "www"
    / "pentair-pump-display-card.js"
)


def test_display_card_matches_rs485_card() -> None:
    assert RS485.is_file()
    assert DISPLAY.is_file()
    assert RS485.read_text(encoding="utf-8") == DISPLAY.read_text(
        encoding="utf-8"
    )


def test_remote_lookup_hints_cover_pump_1() -> None:
    js = RS485.read_text(encoding="utf-8")
    assert "_afficheur_actif" in js
    assert "LOOKUP_DOMAINS" in js
    assert "sensor" in js
