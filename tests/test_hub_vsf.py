"""Unit tests for VSF / multi-pump hub helpers."""

from custom_components.pentair_rs485.hub import PentairHub, PumpConfig, _default_profile
from custom_components.pentair_rs485.rs485.packets import CommandProfile, PumpType


class _FakeBus:
    async def async_open(self) -> None:
        return None

    async def async_close(self) -> None:
        return None


def test_default_profile_by_type():
    assert _default_profile(PumpType.VS) == CommandProfile.RPM
    assert _default_profile(PumpType.VSF) == CommandProfile.RPM
    assert _default_profile(PumpType.VF) == CommandProfile.GPM


def test_vsf_command_profile_switch():
    hub = PentairHub(
        bus=_FakeBus(),  # type: ignore[arg-type]
        app_address=33,
        pumps=[
            PumpConfig(index=1, name="Pool", pump_type=PumpType.VSF),
            PumpConfig(index=2, name="Spa", pump_type=PumpType.VSF),
        ],
    )
    assert hub.get_command_profile(1) == CommandProfile.RPM
    assert hub.get_command_profile(2) == CommandProfile.RPM

    hub.set_command_profile(1, CommandProfile.GPM)
    assert hub.get_command_profile(1) == CommandProfile.GPM
    assert hub.get_target_mode(1) == 1
    assert hub.get_command_profile(2) == CommandProfile.RPM

    hub.set_command_profile(2, CommandProfile.RPM)
    assert hub.get_target_mode(2) == 2


def test_status_dict_includes_command_profile():
    hub = PentairHub(
        bus=_FakeBus(),  # type: ignore[arg-type]
        app_address=33,
        pumps=[PumpConfig(index=1, name="Pool", pump_type=PumpType.VSF)],
    )
    data = hub.status_dict(1, hub.pumps[0])
    assert data["type"] == "VSF"
    assert data["command_profile"] == "rpm"
    assert "program_1_speed" in data
