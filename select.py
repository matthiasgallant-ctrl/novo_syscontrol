from __future__ import annotations

from homeassistant.components.select import SelectEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import CONF_NAME, DOMAIN
from .coordinator import NovoSysControlCoordinator

SOURCES = {
    "hdmi1": "HDMI 1",
    "hdmi2": "HDMI 2",
    "vga": "VGA",
    "android": "Android",
}

async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities
) -> None:
    coordinator: NovoSysControlCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([NovoSourceSelect(coordinator, entry)])


class NovoSourceSelect(CoordinatorEntity, SelectEntity):
    _attr_has_entity_name = True
    _attr_name = "Source"
    _attr_options = list(SOURCES.values())

    def __init__(self, coordinator: NovoSysControlCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator)
        self._entry = entry
        self._attr_unique_id = f"{entry.entry_id}_source"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name=entry.data[CONF_NAME],
            manufacturer="Vivitek / Novo",
            model=entry.data.get("model", "ND-M1000"),
        )

    @property
    def current_option(self) -> str | None:
        raw = (self.coordinator.data or {}).get("source", "")
        key = raw.lower()
        # device may return "VGA" vs "vga"
        for cmd_key, label in SOURCES.items():
            if key == cmd_key:
                return label
        return None

    async def async_select_option(self, option: str) -> None:
        cmd_key = next(k for k, v in SOURCES.items() if v == option)
        # SysControl docs use "VGA" uppercase for set, lowercase in state — try as documented
        source_arg = "VGA" if cmd_key == "vga" else cmd_key
        await self.coordinator.client.send_command(f"source {source_arg}")
        await self.coordinator.async_request_refresh()