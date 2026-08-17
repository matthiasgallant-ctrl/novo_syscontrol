from __future__ import annotations

import logging
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_HOST, CONF_NAME, CONF_PORT
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResult
from homeassistant.exceptions import HomeAssistantError

from .client import NovoSysControlClient, NovoSysControlConnectionError
from .const import CONF_HOST as DOMAIN_HOST, CONF_NAME as DOMAIN_NAME, CONF_PORT as DOMAIN_PORT, DEFAULT_PORT, DOMAIN

_LOGGER = logging.getLogger(__name__)

STEP_USER_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_NAME): str,
        vol.Required(CONF_HOST): str,
        vol.Optional(CONF_PORT, default=DEFAULT_PORT): int,
    }
)


class NovoSysControlConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 1

    async def async_step_user(self, user_input: dict | None = None) -> FlowResult:
        errors: dict[str, str] = {}

        if user_input is not None:
            host = user_input[CONF_HOST]
            port = user_input[CONF_PORT]
            name = user_input[CONF_NAME]

            await self.async_set_unique_id(f"{host}:{port}")
            self._abort_if_unique_id_configured()

            try:
                model = await validate_connection(host, port)
            except CannotConnect:
                errors["base"] = "cannot_connect"
            except InvalidResponse:
                errors["base"] = "invalid_response"
            else:
                return self.async_create_entry(
                    title=name,
                    data={
                        DOMAIN_NAME: name,
                        DOMAIN_HOST: host,
                        DOMAIN_PORT: port,
                        "model": model or "ND-M1000",
                    },
                )

        return self.async_show_form(step_id="user", data_schema=STEP_USER_SCHEMA, errors=errors)


async def validate_connection(host: str, port: int) -> str | None:
    try:
        client = NovoSysControlClient(host, port)
        response, model = await client.send_command("query")
        if not response and not model:
            raise InvalidResponse()
        return model or response
    except NovoSysControlConnectionError:
        raise CannotConnect()

class CannotConnect(HomeAssistantError):
    """Unable to connect."""


class InvalidResponse(HomeAssistantError):
    """Unexpected device response."""