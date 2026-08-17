from __future__ import annotations

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import CONF_NAME, DOMAIN
from .coordinator import NovoSysControlCoordinator


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities) -> None:
    coordinator: NovoSysControlCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        [
            NovoPowerSwitch(coordinator, entry),
            NovoMuteSwitch(coordinator, entry),
        ]
    )


class NovoBaseSwitch(CoordinatorEntity, SwitchEntity):
    _attr_has_entity_name = True

    def __init__(self, coordinator: NovoSysControlCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator)
        self._entry = entry
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name=entry.data[CONF_NAME],
            manufacturer="Vivitek / Novo",
            model=entry.data.get("model", "ND-M1000"),
        )


class NovoPowerSwitch(NovoBaseSwitch):
    _attr_name = "Power"
    _attr_unique_id = None  # set in __init__

    def __init__(self, coordinator, entry):
        super().__init__(coordinator, entry)
        self._attr_unique_id = f"{entry.entry_id}_power"

    @property
    def is_on(self) -> bool:
        return self.coordinator.data.get("power") == "wakeup"

    async def async_turn_on(self, **kwargs) -> None:
        await self.coordinator.client.send_command("wakeup")
        await self.coordinator.async_request_refresh()

    async def async_turn_off(self, **kwargs) -> None:
        await self.coordinator.client.send_command("standby")
        await self.coordinator.async_request_refresh()


class NovoMuteSwitch(NovoBaseSwitch):
    _attr_name = "Mute"

    def __init__(self, coordinator, entry):
        super().__init__(coordinator, entry)
        self._attr_unique_id = f"{entry.entry_id}_mute"

    @property
    def is_on(self) -> bool:
        return bool(self.coordinator.data.get("mute"))

    async def async_turn_on(self, **kwargs) -> None:
        await self.coordinator.client.send_command("mute")
        await self.coordinator.async_request_refresh()

    async def async_turn_off(self, **kwargs) -> None:
        await self.coordinator.client.send_command("unmute")
        await self.coordinator.async_request_refresh()