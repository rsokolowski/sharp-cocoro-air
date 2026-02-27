# Sharp COCORO Air — HACS Custom Integration

## What This Is

A Home Assistant custom integration (HACS-compatible) for Sharp air purifiers sold in Europe. It communicates via the Sharp COCORO Air EU cloud API — the same backend the official Sharp Life AIR EU mobile app uses.

## Repository Structure

```
custom_components/sharp_cocoro_air/
  __init__.py        # Entry point: setup/unload config entry
  api.py             # Sharp EU cloud API client (sync httpx, run in executor)
  config_flow.py     # UI config flow (email/password) + options flow (polling interval)
  const.py           # Domain, platform list, mode maps, scan interval constants
  coordinator.py     # DataUpdateCoordinator — polling, commands, optimistic updates
  entity.py          # Base entity class with shared device_info
  fan.py             # FanEntity: power on/off + 8 preset modes
  sensor.py          # 11 SensorEntity types (temp, humidity, dust, etc.)
  switch.py          # SwitchEntity: humidification toggle
  manifest.json      # HA integration metadata
  strings.json       # Translation source strings
  translations/      # en.json, pl.json

sharp_api.py         # Standalone CLI client (same API, used for manual testing)
hacs.json            # HACS repository metadata
```

## Architecture

### API Flow (required order)

1. `setting/terminalAppId/` — GET → obtain a terminal app ID (TAI)
2. `setting/login/` — POST with OAuth auth code + password nonce
3. `setting/userInfo` — GET user profile
4. `setting/terminal` — POST to register terminal (enables control endpoints)
5. `setting/pairing/` — POST per box (enables GET endpoints with boxId)
6. `setting/boxInfo` — GET with `mode=other` → returns all device data + ECHONET properties
7. `control/deviceControl` — POST to send commands (power, mode, humidify)

### Key Patterns

- **Sync API in executor**: `api.py` uses synchronous `httpx.Client`. All calls go through `hass.async_add_executor_job()`.
- **Lazy client init**: `httpx.Client` is created on first use via `_ensure_client()` to avoid blocking the event loop during `__init__`.
- **DataUpdateCoordinator**: `coordinator.py` handles polling, auth refresh, and exposes async command methods.
- **Optimistic updates**: After sending a command, the coordinator immediately updates local state via `async_set_updated_data()` before the next poll confirms it.
- **Startup retries**: The coordinator retries `full_init()` up to 3 times with 10s delays to handle transient network issues during HA boot.
- **Options reload**: Changing the polling interval in the UI triggers a full integration reload.

### ECHONET Lite Properties

Sensor data is encoded in `echonetProperty` hex blobs using ECHONET Lite TLV format. Key property codes:

- **F1** (State Detail): temperature, humidity, dust, smell, PCI, light, filter usage
- **F3** (Operation Mode): current mode byte at offset 4, humidification at offset 15
- **80** (Power): on/off state
- **84** (Power Consumption): current watts
- **85** (Energy): cumulative Wh

## Important Gotchas

- **TAI slot limit**: Max 5 terminal app IDs per box. The integration uses `appName=spremote_ha_eu:1:1.0.0` to distinguish its TAIs from the phone app's (`spremote_a_eu:1:*`). On startup, it cleans up stale HA TAIs but never touches phone app entries.
- **F3 byte 15 for humidification**: Not byte 12 — confirmed by matching the set_humidify control command payload.
- **Terminal registration is required**: Without the `setting/terminal` POST, all `control/` POST requests return 400.
- **Pairing is required**: Without `setting/pairing/` per box, GET requests with boxId fail.

## Conventions

- Follow standard Home Assistant integration patterns (coordinator, entity base class, config flow)
- Entity names come from `strings.json` translations, not hardcoded `_attr_name`
- All entities use `_attr_has_entity_name = True` and `translation_key`
- No PyPI dependencies — `httpx` is a HA core dependency

## Testing

No automated tests. Verify manually:

1. Deploy files to the HA server's `custom_components/` directory
2. Restart Home Assistant
3. Check that the integration loads and all 13 entities per device appear
4. Test fan power toggle, mode changes, and humidification switch
5. Verify sensor values update at the configured polling interval
