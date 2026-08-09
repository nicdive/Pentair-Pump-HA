# Pentair Pump HA

Home Assistant custom integration for standalone **Pentair IntelliFlo** pump control over **RS485**.

## Current version

**v0.5.2**

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

## Notes

- Designed for direct RS485 control (no EasyTouch/IntelliCenter required)
- Multiple pumps can share one USB RS485 adapter (different pump addresses)
- Field-tested on IntelliFlo VF WhisperFlo
