"""Sensor platform for Novo Syscontrol."""
from __future__ import annotations

import logging
from typing import Any  # Toegevoegd voor Any

from homeassistant.components.sensor import (
    SensorEntity,
    SensorEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
)

_LOGGER = logging.getLogger(__name__)

SENSOR_TYPES: tuple[SensorEntityDescription, ...] = (
    SensorEntityDescription(
        key="power",  # Aangepast naar "power" om te matchen met client.py
        name="Power State",
        icon="mdi:power",
    ),
    SensorEntityDescription(
        key="source",  # TOEGEVOEGD: Nu verschijnt de Source-sensor wél!
        name="Source",
        icon="mdi:import",
    ),
    SensorEntityDescription(
        key="model",
        name="Model",
        icon="mdi:device-information",
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
)

async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the sensor platform."""
    # Hier komt later je code om sensoren toe te voegen
    domain_data = hass.data.get("novo_syscontrol", {})
    coordinator = domain_data.get(config_entry.entry_id)
    if coordinator is None:
        _LOGGER.error("Data update coordinator niet gevonden voor deze entry")
        return
    entities = [
        NovoSyscontrolSensor(coordinator, description, config_entry) for description in SENSOR_TYPES
    ] 
    async_add_entities(entities)

class NovoSyscontrolSensor(CoordinatorEntity, SensorEntity):
    """Representatie van een Novo Syscontrol Sensor."""
    def __init__(
    self,
    coordinator: DataUpdateCoordinator[Any],
    description: SensorEntityDescription,
    config_entry: ConfigEntry,
    ) -> None:
        """Initialiseer de sensor en koppel deze aan de coordinator."""
        super().__init__(coordinator)
        self.entity_description = description
        self._config_entry = config_entry
        self._attr_unique_id = f"{config_entry.entry_id}{description.key}"
        self._attr_device_info = {
            "identifiers": {("novo_syscontrol", config_entry.entry_id)},
            "name": config_entry.title,
            "manufacturer": "Novo",
        }
    @property
    def native_value(self) -> str | bool | None:
        data = self.coordinator.data
        if not data or not isinstance(data, dict):
            return None 
            
        # Haal direct de waarde op die matcht met de 'key' uit SENSOR_TYPES
        value = data.get(self.entity_description.key)
        
        # Maak de tekst netjes voor de UI (bijv. 'wakeup' -> 'Wakeup')
        if isinstance(value, str):
            return value.capitalize()
            
        return value
pass
