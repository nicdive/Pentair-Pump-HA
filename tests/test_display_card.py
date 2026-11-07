"""Lovelace pump-display card: program keys instead of more-info."""

from pathlib import Path

CARD = (
    Path(__file__).resolve().parents[1]
    / "custom_components"
    / "pentair_rs485"
    / "www"
    / "pentair-pump-display-card.js"
)


def _src() -> str:
    return CARD.read_text(encoding="utf-8")


def test_card_has_no_entites_button() -> None:
    src = _src()
    assert "Entités" not in src
    assert "hass-more-info" not in src
    assert 'data-act="more"' not in src


def test_card_has_four_program_buttons() -> None:
    src = _src()
    assert 'data-act="prog${n}"' in src
    assert "[1, 2, 3, 4]" in src
    assert 'callService("button", "press"' in src
    assert "_lancer_programme_1" in src
    assert "run_program_1" in src


def test_active_program_parses_mode_labels() -> None:
    src = _src()
    assert "function activeProgram" in src
    assert "ext_program_" in src
    assert "programme" in src


def test_card_guards_double_define() -> None:
    src = _src()
    assert "if (!customElements.get(CARD_TYPE))" in src
    assert "customElements.define(CARD_TYPE" in src
