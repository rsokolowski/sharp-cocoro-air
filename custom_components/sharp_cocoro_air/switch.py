"""Switch platform for Sharp COCORO Air."""
from __future__ import annotations

from typing import Any

from homeassistant.components.switch import SwitchDeviceClass, SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .coordinator import SharpCocoroAirCoordinator
from .entity import SharpCocoroAirEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Sharp switch entities."""
    coordinator: SharpCocoroAirCoordinator = entry.runtime_data
    async_add_entities(
        SharpHumidificationSwitch(coordinator, device_id)
        for device_id in coordinator.data
    )


class SharpHumidificationSwitch(SharpCocoroAirEntity, SwitchEntity):
    """Switch to toggle humidification on/off."""

    _attr_device_class = SwitchDeviceClass.SWITCH
    _attr_translation_key = "humidification"

    def __init__(
        self, coordinator: SharpCocoroAirCoordinator, device_id: str,
    ) -> None:
        super().__init__(coordinator, device_id)
        self._attr_unique_id = f"{device_id}_humidification"

    @property
    def is_on(self) -> bool | None:
        return self.device_properties.get("humidify")

    async def async_turn_on(self, **kwargs: Any) -> None:
        if (device := self.device_data) is None:
            return
        await self.coordinator.async_set_humidify(device, True)

    async def async_turn_off(self, **kwargs: Any) -> None:
        if (device := self.device_data) is None:
            return
        await self.coordinator.async_set_humidify(device, False)
