# Pentair Pump HA

Home Assistant custom integration for standalone **Pentair IntelliFlo** pump control over **RS485**.

## Current version

**v0.6.4**

## Install

1. Copy `custom_components/pentair_rs485` into `/config/custom_components/`
2. Or unzip a release from `releases/pentair_rs485_vX.Y.Z.zip` into `custom_components/`
3. Restart Home Assistant
4. Add integration **Pentair RS485**

## Releases

```bash
./build_release.sh
```

## Features

- IntelliFlo **VS**, **VF**, **VSF**
- Multiple pumps on one adapter (indexes → addresses 96–111)
- Mode select, programs 1–4, RPM/GPM, cover-open boost
- Sensors: watts, RPM, GPM, mode, drive, filter %, timer, clock, error
- Binary sensors: RS485 online, cover boost active
- **Panel control** switch: ON = physical pump buttons (persisted); OFF = HA remote
- Reconfigure: port / pumps (integration → ⋮ → Reconfigure)
- Options: pool cover sensor for boost

## Resilience

- **`desired_run`**: if you stop the pump in HA before a restart, it will **not** auto-start after reboot
- If it was running (`desired_run=true`), setpoint is resumed after HA start
- Watchdog restores mode + RPM/GPM after a pump power blip
- USB RS485 reconnect on I/O failure
- Cover `unavailable` ignored; boost snapshot restored across HA restart
- **Panel control** switch persists across reboot; while ON, HA commands / watchdog / cover boost are idle

## Schedules / temperature curves

Use Home Assistant automations (not written into the pump).
