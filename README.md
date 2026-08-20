# Pentair Pump HA

Home Assistant custom integration for standalone **Pentair IntelliFlo** pump control over **RS485**.

## Current version

**v0.6.1**

## Install

1. Copy `custom_components/pentair_rs485` into `/config/custom_components/`
2. Or unzip a release from `releases/pentair_rs485_vX.Y.Z.zip` into `custom_components/`
3. Restart Home Assistant
4. Add integration **Pentair RS485**

## Releases

Versioned zips are in [`releases/`](releases/).

```bash
./build_release.sh
```

## Features

- IntelliFlo **VS**, **VF**, **VSF** (VSF: RPM or GPM via command profile)
- Multiple pumps on one USB RS485 adapter (indexes → addresses 96–111)
- Mode select, program buttons 1–4, RPM/GPM setpoints
- Sensors: watts, RPM, GPM, mode, drive state, **filter % (PPC)**, program timer, clock, error
- **Cover boost**: configure a cover/binary_sensor in *Configure* → enable *Cover boost* switch → set boost speed (RPM/GPM). Opens cover → boost; closes → restore previous speed

## Resilience (power / HA restart)

- **Watchdog**: if HA still considers the pump should run, restores mode **and** last RPM/GPM after a pump power blip
- **HA restart**: learns live RPM/mode from the pump so watchdog keeps working; cover-boost switch/consigne/snapshot are restored; boost re-applies if the cover is still open
- Cover sensor `unavailable`/`unknown` is ignored (does not fake a close)
- Hourly schedules remain HA-side (Automations / Schedule)

## Notes

- Field-tested on IntelliFlo VF WhisperFlo; VSF uses the same RS485 command set
