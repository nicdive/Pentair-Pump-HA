"""Lovelace resource registration helpers (HA 2026.8+)."""

from custom_components.pentair_rs485.frontend import (
    _CARD_VERSION,
    _LOCAL_URL,
    pick_resource_update,
    resource_bases,
)


def test_local_url_is_marketplace_path() -> None:
    assert _LOCAL_URL.startswith("/local/community/pentair_rs485/")
    assert f"?v={_CARD_VERSION}" in _LOCAL_URL
    assert _CARD_VERSION == "0.8.2"


def test_pick_creates_when_missing() -> None:
    item_id, current = pick_resource_update([], _LOCAL_URL)
    assert item_id is None
    assert current is False


def test_pick_skips_when_already_current() -> None:
    items = [{"id": "abc", "url": _LOCAL_URL}]
    item_id, current = pick_resource_update(items, _LOCAL_URL)
    assert item_id == "abc"
    assert current is True


def test_pick_updates_stale_version_and_old_static_path() -> None:
    stale = f"/pentair_rs485/pentair-pump-display-card.js?v=0.8.1"
    items = [{"id": 7, "url": stale}]
    item_id, current = pick_resource_update(items, _LOCAL_URL)
    assert item_id == 7
    assert current is False
    assert "/pentair_rs485/pentair-pump-display-card.js" in resource_bases()
