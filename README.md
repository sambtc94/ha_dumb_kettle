# Dumb Kettle

A Home Assistant custom integration that monitors a "dumb" (non-smart) kettle using a power monitoring plug or sensor. It tracks when the kettle is boiling, records boil durations, counts total boils, and fires a binary sensor trigger when a boil completes — perfect for automations.

## Features

- **Kettle State sensor** — reports `idle` or `boiling`, with a live icon swap
- **Last Boil Duration sensor** — duration (in seconds) of the most recent boil
- **Boil Count sensor** — total number of boils recorded since the integration was added
- **Boil Complete binary sensor** — turns `ON` for a configurable window after the kettle finishes, ideal as an automation trigger

## Requirements

- Home Assistant 2024.1.0 or newer
- A power monitoring sensor (e.g. a smart plug with a `power` device class sensor) connected to your kettle

## Installation

### Via HACS (recommended)

1. Open HACS → **Integrations** → ⋮ → **Custom repositories**
2. Add `https://github.com/sambtc94/ha_dumb_kettle` with category **Integration**
3. Search for **Dumb Kettle** and install it
4. Restart Home Assistant

### Manual

1. Copy the `custom_components/ha_dumb_kettle` folder into your `<config>/custom_components/` directory
2. Restart Home Assistant

## Configuration

Go to **Settings → Devices & Services → Add Integration** and search for **Dumb Kettle**.

| Field | Default | Description |
|---|---|---|
| Name | `Kettle` | Friendly name for the device |
| Power sensor | — | The `sensor` entity with device class `power` on your kettle plug |
| Boiling threshold | `1000 W` | Power above this value means the kettle is boiling |
| Idle threshold | `50 W` | Power below this value means the kettle is idle |
| Minimum boil duration | `10 s` | Boils shorter than this are ignored (filters out accidental clicks) |
| Boil complete window | `30 s` | How long the **Boil Complete** binary sensor stays `ON` after a boil |

All thresholds can be updated later via the integration's **Configure** button without removing and re-adding it.

## Entities

| Entity | Type | Description |
|---|---|---|
| `sensor.<name>_state` | Sensor | Current state: `idle` or `boiling` |
| `sensor.<name>_last_boil_duration` | Sensor | Duration of the last boil in seconds |
| `sensor.<name>_boil_count` | Sensor | Total boils counted since the integration loaded |
| `binary_sensor.<name>_boil_complete` | Binary sensor | `ON` briefly after each boil completes |

## Automation example

Send a mobile notification when the kettle is ready:

```yaml
automation:
  - alias: "Kettle ready notification"
    trigger:
      - platform: state
        entity_id: binary_sensor.kettle_boil_complete
        to: "on"
    action:
      - service: notify.mobile_app_your_phone
        data:
          message: "☕ Kettle has boiled!"
```
