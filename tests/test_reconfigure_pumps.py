"""Reconfigure keep/remove pumps and leftover device cleanup."""

from custom_components.pentair_rs485.const import (
    CONF_PUMP_INDEX,
    CONF_PUMP_NAME,
    CONF_PUMP_TYPE,
)
from custom_components.pentair_rs485.device_cleanup import (
    device_pump_index,
    filter_kept_pumps,
    should_remove_device,
    should_remove_entity,
    unique_id_pump_index,
)


def _pump(index: int, name: str, pump_type: str = "VF") -> dict:
    return {
        CONF_PUMP_INDEX: index,
        CONF_PUMP_NAME: name,
        CONF_PUMP_TYPE: pump_type,
    }


def test_filter_keeps_selected_indexes_only() -> None:
    pumps = [_pump(1, "Pompe 1", "VF"), _pump(2, "Pool Pump", "VS")]
    kept = filter_kept_pumps(pumps, ["1"])
    assert kept == [_pump(1, "Pompe 1", "VF")]


def test_filter_empty_keep_drops_all() -> None:
    pumps = [_pump(1, "Pompe 1"), _pump(2, "Pool Pump", "VS")]
    assert filter_kept_pumps(pumps, []) == []


def test_filter_accepts_single_int() -> None:
    pumps = [_pump(1, "A"), _pump(2, "B")]
    assert filter_kept_pumps(pumps, 2) == [_pump(2, "B")]


def test_filter_none_keeps_all() -> None:
    pumps = [_pump(1, "A"), _pump(2, "B")]
    assert filter_kept_pumps(pumps, None) == pumps


def test_unique_id_pump_index() -> None:
    entry = "abc123"
    assert unique_id_pump_index(entry, "abc123_1_power") == 1
    assert unique_id_pump_index(entry, "abc123_2_rpm") == 2
    assert unique_id_pump_index(entry, "abc123_bus_online") is None
    assert unique_id_pump_index(entry, "other_1_power") is None


def test_device_pump_index_ignores_hub() -> None:
    entry = "abc123"
    assert device_pump_index(entry, {("pentair_rs485", "abc123_bus")}) is None
    assert device_pump_index(entry, {("pentair_rs485", "abc123_2")}) == 2


def test_should_remove_orphan_vs_keep_vf() -> None:
    entry = "abc123"
    keep = {1}
    assert should_remove_entity(entry, "abc123_2_power", keep) is True
    assert should_remove_entity(entry, "abc123_1_power", keep) is False
    assert should_remove_entity(entry, "abc123_bus_online", keep) is False
    assert (
        should_remove_device(entry, {("pentair_rs485", "abc123_2")}, keep)
        is True
    )
    assert (
        should_remove_device(entry, {("pentair_rs485", "abc123_1")}, keep)
        is False
    )
    assert (
        should_remove_device(entry, {("pentair_rs485", "abc123_bus")}, keep)
        is False
    )
