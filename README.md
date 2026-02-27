# Sharp COCORO Air

[![HACS Custom](https://img.shields.io/badge/HACS-Custom-41BDF5.svg)](https://hacs.xyz)
[![Home Assistant](https://img.shields.io/badge/Home%20Assistant-2024.8%2B-41BDF5.svg)](https://www.home-assistant.io)

Home Assistant custom integration for **Sharp air purifiers** sold in Europe. Communicates with devices through the Sharp COCORO Air EU cloud — the same backend used by the official **Sharp Life AIR EU** mobile app.

## Supported Devices

Tested with the **Sharp KI-N52** (KIN52). Other models in the KI-N series that use the Sharp Life AIR EU app should also work.

## Features

- **Fan entity** — power on/off with 8 preset modes:
  Auto, Night, Pollen, Silent, Medium, High, AI Auto, Turbo Clean
- **Humidification switch** — toggle the built-in humidifier
- **11 sensors** per device — see [Entities](#entities) below
- **Configurable polling interval** — 15 to 300 seconds (default 60s)
- **UI config flow** — set up entirely from the Home Assistant frontend
- **Translations** — English and Polish

## Prerequisites

1. A **Sharp Members EU** account (register via the Sharp Life AIR EU app)
2. Your air purifier(s) paired in the Sharp Life AIR EU app
3. [HACS](https://hacs.xyz) installed in your Home Assistant instance

## Installation

1. Open HACS in Home Assistant
2. Click the three-dot menu (top right) → **Custom repositories**
3. Add the repository URL, select category **Integration**, and click **Add**
4. Search for **Sharp COCORO Air** in HACS and click **Download**
5. Restart Home Assistant

## Configuration

### Initial Setup

1. Go to **Settings → Devices & Services → Add Integration**
2. Search for **Sharp COCORO Air**
3. Enter your Sharp Members EU email and password
4. All paired devices are discovered automatically

### Options

After setup, click **Configure** on the integration to adjust:

| Option | Default | Range | Description |
|--------|---------|-------|-------------|
| Polling interval | 60s | 15–300s | How often to fetch data from the Sharp cloud |

## Entities

Each device exposes **13 entities**:

| Entity | Type | Description |
|--------|------|-------------|
| Air Purifier | Fan | Power on/off and preset mode selection |
| Humidification | Switch | Toggle the built-in humidifier |
| Temperature | Sensor | Room temperature (°C) |
| Humidity | Sensor | Room humidity (%) |
| Power Consumption | Sensor | Current power draw (W) |
| Energy | Sensor | Cumulative energy usage (kWh) |
| Dust Level | Sensor | Particulate matter reading |
| Smell Level | Sensor | Odor/VOC sensor reading |
| PCI Sensor | Sensor | Plasmacluster Ion concentration |
| Light Sensor | Sensor | Ambient light level |
| Filter Usage | Sensor | Filter runtime (hours) |
| Cleaning Mode | Sensor | Current cleaning mode |
| Airflow | Sensor | Current airflow level |

### Preset Modes

| Mode | Description |
|------|-------------|
| Auto | Automatic adjustment based on sensors |
| Night | Quiet night-time operation |
| Pollen | Optimized for pollen removal |
| Silent | Lowest noise level |
| Medium | Medium fan speed |
| High | High fan speed |
| AI Auto | AI-driven automatic mode |
| Turbo Clean | Intensive cleaning cycle (max fan then boosted auto) |

## Known Limitations

- **Cloud-only** — there is no local API; all communication goes through the Sharp EU cloud
- **Polling** — the cloud does not support push notifications to third-party clients, so data is fetched at the configured interval
- **EU region only** — this integration uses the Sharp Members EU endpoint; other regions are not supported
- **Session slots** — the Sharp cloud allows a maximum of 5 active sessions per device; the integration manages its own slot automatically

## License

[MIT](LICENSE)
