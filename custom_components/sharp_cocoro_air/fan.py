"""Fan platform for Sharp COCORO Air."""
from __future__ import annotations

from typing import Any

from homeassistant.components.fan import FanEntity, FanEntityFeature
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DISPLAY_TO_API_MODE, OPERATION_MODES
from .coordinator import SharpCocoroAirCoordinator
from .entity import SharpCocoroAirEntity

PRESET_MODES = list(OPERATION_MODES.keys())


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Sharp fan entities."""
    coordinator: SharpCocoroAirCoordinator = entry.runtime_data
    async_add_entities(
        SharpAirPurifierFan(coordinator, device_id)
        for device_id in coordinator.data
    )


class SharpAirPurifierFan(SharpCocoroAirEntity, FanEntity):
    """Fan entity representing a Sharp air purifier."""

    _attr_supported_features = (
        FanEntityFeature.TURN_ON
        | FanEntityFeature.TURN_OFF
        | FanEntityFeature.PRESET_MODE
    )
    _attr_translation_key = "air_purifier"

    def __init__(
        self, coordinator: SharpCocoroAirCoordinator, device_id: str,
    ) -> None:
        super().__init__(coordinator, device_id)
        self._attr_unique_id = f"{device_id}_fan"

    @property
    def is_on(self) -> bool | None:
        power = self.device_properties.get("power")
        if power is None:
            return None
        return power == "on"

    @property
    def preset_mode(self) -> str | None:
        mode_display = self.device_properties.get("operation_mode")
        if mode_display is None:
            return None
        # operation_mode from ECHONET decode is display name ("Auto"),
        # convert to API key ("auto")
        return DISPLAY_TO_API_MODE.get(mode_display, mode_display.lower())

    @property
    def preset_modes(self) -> list[str]:
        return PRESET_MODES

    async def async_turn_on(
        self,
        percentage: int | None = None,
        preset_mode: str | None = None,
        **kwargs: Any,
    ) -> None:
        await self.coordinator.async_power_on(self.device_data)
        if preset_mode is not None:
            await self.coordinator.async_set_mode(self.device_data, preset_mode)

    async def async_turn_off(self, **kwargs: Any) -> None:
        await self.coordinator.async_power_off(self.device_data)

    async def async_set_preset_mode(self, preset_mode: str) -> None:
        await self.coordinator.async_set_mode(self.device_data, preset_mode)
