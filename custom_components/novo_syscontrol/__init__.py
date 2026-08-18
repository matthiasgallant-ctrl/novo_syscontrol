from __future__ import annotations

import logging
import asyncio
import importlib

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.typing import ConfigType

from .client import NovoSysControlClient
from .const import (
    ATTR_PLAYLIST,
    CONF_HOST,
    CONF_NAME,
    CONF_PORT,
    DEFAULT_PORT,
    DOMAIN,
    SERVICE_PLAY_PLAYLIST,
    SERVICE_SEND_COMMAND,
)
from .coordinator import NovoSysControlCoordinator

_LOGGER = logging.getLogger(__name__)

PLATFORMS = [
    Platform.SWITCH, # power, mute
    Platform.NUMBER, # volume, backlight
    Platform.SELECT, # source
    Platform.SENSOR, # diagnostics
]

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)

async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:

    async def handle_send_command(call):
        coordinator = _get_coordinator(hass, call.data["entry_id"])
        command = call.data["command"]

        await coordinator.client.send_command(command)
        await coordinator.async_request_refresh()

    hass.services.async_register(
        DOMAIN,
        SERVICE_SEND_COMMAND,
        handle_send_command,
    )

    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    host = entry.data[CONF_HOST]
    port = entry.data.get(CONF_PORT, DEFAULT_PORT)
    name = entry.data[CONF_NAME]

    client = NovoSysControlClient(host, port)
    coordinator = NovoSysControlCoordinator(hass, client, name)
    await coordinator.async_config_entry_first_refresh()

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)
    return unload_ok


def _get_coordinator(hass: HomeAssistant, entry_id: str) -> NovoSysControlCoordinator:
    return hass.data[DOMAIN][entry_id]
