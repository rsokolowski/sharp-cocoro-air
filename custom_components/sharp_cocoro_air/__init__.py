"""The Sharp COCORO Air integration."""
from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import PLATFORMS
from .coordinator import SharpCocoroAirCoordinator

type SharpCocoroAirConfigEntry = ConfigEntry[SharpCocoroAirCoordinator]


async def async_setup_entry(
    hass: HomeAssistant, entry: SharpCocoroAirConfigEntry,
) -> bool:
    """Set up Sharp COCORO Air from a config entry."""
    coordinator = SharpCocoroAirCoordinator(hass, entry)
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = coordinator
    entry.async_on_unload(coordinator.api.close)
    entry.async_on_unload(entry.add_update_listener(_async_options_updated))
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def _async_options_updated(
    hass: HomeAssistant, entry: SharpCocoroAirConfigEntry,
) -> None:
    """Reload integration when options change."""
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(
    hass: HomeAssistant, entry: SharpCocoroAirConfigEntry,
) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
