"""Number platform for Novo Syscontrol."""
from __future__ import annotations
import logging
from typing import Any
from homeassistant.components.number import NumberEntity, NumberMode
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
)

_LOGGER = logging.getLogger(__name__)
async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Novo Syscontrol number platform."""
    domain_data = hass.data.get("novo_syscontrol", {})
    coordinator = domain_data.get(config_entry.entry_id)
    if coordinator is None:
        _LOGGER.error("Data update coordinator niet gevonden voor number platform")
        return
    async_add_entities([
        NovoVolumeNumber(coordinator, config_entry),
        NovoBacklightNumber(coordinator, config_entry)
    ])    

class NovoVolumeNumber(CoordinatorEntity, NumberEntity):
    _attr_has_entity_name = True
    _attr_name = "Volume"
    _attr_native_min_value = 0
    _attr_native_max_value = 100
    _attr_native_step = 1
    _attr_mode = NumberMode.SLIDER

    def __init__(self, coordinator: DataUpdateCoordinator[Any], config_entry: ConfigEntry) -> None:
        """Initialiseer de volume entiteit."""
        super().__init__(coordinator)
        self._config_entry = config_entry
        self._attr_unique_id = f"{config_entry.entry_id}_volume"
        self._attr_device_info = {
            "identifiers": {("novo_syscontrol", config_entry.entry_id)},
            "name": config_entry.title,
            "manufacturer": "Novo",
        }

    @property
    def native_value(self) -> float | None:
        return self.coordinator.data.get("volume")

    async def async_set_native_value(self, value: float) -> None:
        await self.coordinator.client.send_command(f"volume {int(value)}")
        await self.coordinator.async_request_refresh()

class NovoBacklightNumber(CoordinatorEntity, NumberEntity):
    _attr_has_entity_name = True
    _attr_name = "Backlight"
    _attr_native_min_value = 0
    _attr_native_max_value = 100
    _attr_native_step = 1
    _attr_mode = NumberMode.SLIDER
    def __init__(self, coordinator: DataUpdateCoordinator[Any], config_entry: ConfigEntry) -> None:
        """Initialiseer de backlight entiteit."""
        super().__init__(coordinator)
        self._config_entry = config_entry
        self._attr_unique_id = f"{config_entry.entry_id}_backlight"
        self._attr_device_info = {
            "identifiers": {("novo_syscontrol", config_entry.entry_id)},
            "name": config_entry.title,
            "manufacturer": "Novo",
        }
    @property
    def native_value(self) -> float | None:
        return self.coordinator.data.get("backlight")

    async def async_set_native_value(self, value: float) -> None:
        await self.coordinator.client.send_command(f"backlight {int(value)}")
        await self.coordinator.async_request_refresh()