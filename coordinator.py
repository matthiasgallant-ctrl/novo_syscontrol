from __future__ import annotations

import logging

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .client import NovoSysControlClient, NovoSysControlConnectionError
from .const import DEFAULT_SCAN_INTERVAL, DOMAIN
from datetime import timedelta

_LOGGER = logging.getLogger(__name__)


class NovoSysControlCoordinator(DataUpdateCoordinator[dict]):
    def __init__(
        self,
        hass: HomeAssistant,
        client: NovoSysControlClient,
        name: str,
        scan_interval: int = DEFAULT_SCAN_INTERVAL,
    ) -> None:
        super().__init__(
            hass,
            _LOGGER,
            name=f"{DOMAIN}_{name}",
            update_interval=timedelta(seconds=scan_interval),  # add: from datetime import timedelta
        )
        self.client = client

    async def _async_update_data(self) -> dict:
        try:
            return await self.client.get_status()
        except NovoSysControlConnectionError as err:
            raise UpdateFailed(str(err)) from err