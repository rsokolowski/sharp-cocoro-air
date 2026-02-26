"""DataUpdateCoordinator for Sharp COCORO Air."""
from __future__ import annotations

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, HomeAssistantError
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import SharpAPI, SharpApiError, SharpAuthError, SharpConnectionError
from .const import CONF_EMAIL, CONF_PASSWORD, DOMAIN, SCAN_INTERVAL

_LOGGER = logging.getLogger(__name__)


class SharpCocoroAirCoordinator(DataUpdateCoordinator[dict[str, dict]]):
    """Coordinator that polls Sharp cloud API for device data.

    self.data maps device_id (str) -> device dict from SharpAPI.get_devices().
    """

    config_entry: ConfigEntry

    def __init__(self, hass: HomeAssistant, config_entry: ConfigEntry) -> None:
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            config_entry=config_entry,
            update_interval=SCAN_INTERVAL,
        )
        self.api = SharpAPI(
            config_entry.data[CONF_EMAIL],
            config_entry.data[CONF_PASSWORD],
        )

    async def _async_setup(self) -> None:
        """Perform initial login sequence (runs once during first refresh)."""
        try:
            await self.hass.async_add_executor_job(self.api.full_init)
        except SharpAuthError as err:
            raise ConfigEntryAuthFailed("Sharp login failed") from err
        except SharpConnectionError as err:
            raise UpdateFailed(f"Cannot connect to Sharp cloud: {err}") from err

    async def _async_update_data(self) -> dict[str, dict]:
        """Fetch device data from Sharp cloud API."""
        try:
            devices = await self.hass.async_add_executor_job(self.api.get_devices)
        except SharpAuthError:
            # Session expired — attempt automatic re-login
            _LOGGER.info("Sharp session expired, attempting re-login")
            try:
                await self.hass.async_add_executor_job(self.api.full_init)
                devices = await self.hass.async_add_executor_job(self.api.get_devices)
            except SharpAuthError as err:
                raise ConfigEntryAuthFailed("Re-login failed") from err
            except SharpConnectionError as err:
                raise UpdateFailed(
                    f"Error communicating with Sharp cloud: {err}"
                ) from err
        except SharpConnectionError as err:
            raise UpdateFailed(
                f"Error communicating with Sharp cloud: {err}"
            ) from err

        return {str(dev["device_id"]): dev for dev in devices}

    async def _async_control(self, fn, *args) -> None:
        """Run a control command with error handling."""
        try:
            await self.hass.async_add_executor_job(fn, *args)
        except SharpAuthError as err:
            raise ConfigEntryAuthFailed("Session expired") from err
        except (SharpConnectionError, SharpApiError) as err:
            raise HomeAssistantError(f"Command failed: {err}") from err
        await self.async_request_refresh()

    async def async_power_on(self, device: dict) -> None:
        """Turn device on."""
        await self._async_control(self.api.power_on, device)

    async def async_power_off(self, device: dict) -> None:
        """Turn device off."""
        await self._async_control(self.api.power_off, device)

    async def async_set_mode(self, device: dict, mode: str) -> None:
        """Set operation mode."""
        await self._async_control(self.api.set_mode, device, mode)

    async def async_set_humidify(self, device: dict, on: bool) -> None:
        """Toggle humidification."""
        await self._async_control(self.api.set_humidify, device, on)
