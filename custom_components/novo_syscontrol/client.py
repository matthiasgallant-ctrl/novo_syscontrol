from __future__ import annotations

import asyncio
import logging
import re

from .const import COMMAND_TIMEOUT, CONNECT_TIMEOUT, DEFAULT_PORT, GREETING_MARKER, GREETING_TIMEOUT

_LOGGER = logging.getLogger(__name__)

MODEL_RE = re.compile(r"\[([^\]]+)\]")
GET_COMMANDS = {"powerstate", "sourcestate", "volstate", "mutestate", "blstate", "query"}
POWER_COMMAND_ATTEMPTS = 2
POWER_STATE_CHECKS = 5
POWER_CHECK_INTERVAL = 1.0


class NovoSysControlError(Exception):
    """Base error."""


class NovoSysControlConnectionError(NovoSysControlError):
    """Connection or handshake failed."""


class NovoSysControlCommandError(NovoSysControlError):
    """The screen did not reach the requested state."""


class NovoSysControlClient:
    """Async TCP client for Novo SysControl."""

    def __init__(self, host: str, port: int = DEFAULT_PORT) -> None:
        self.host = host
        self.port = port
        self._lock = asyncio.Lock()

    async def send_command(self, command: str) -> tuple[str, str | None]:
        """Serialize commands with polling on this screen."""
        async with self._lock:
            return await self._send_command(command)

    async def _send_command(self, command: str) -> tuple[str, str | None]:
        """Send a command while the caller holds the device lock."""
        command = command.strip()
        if not command or "\n" in command or "\r" in command:
            raise NovoSysControlCommandError("Provide one non-empty command")
        _LOGGER.debug("Sending %r to %s:%s", command, self.host, self.port)

        try:
            reader, writer = await asyncio.wait_for(
                asyncio.open_connection(self.host, self.port),
                timeout=CONNECT_TIMEOUT,
            )
        except (TimeoutError, OSError) as err:
            raise NovoSysControlConnectionError(f"Cannot connect to {self.host}:{self.port}") from err

        try:
            greeting = await self._read_greeting(reader)
            model = self._parse_model(greeting)
            _LOGGER.debug("Greeting from %s: %r", self.host, greeting)

            payload = (command + "\n").encode("ascii")
            writer.write(payload)
            await writer.drain()

            response = await self._read_response(reader, required=command in GET_COMMANDS)
            _LOGGER.debug("Response from %s for %r: %r", self.host, command, response)
            return response, model
        except OSError as err:
            raise NovoSysControlConnectionError(f"Communication failed with {self.host}:{self.port}") from err
        finally:
            writer.close()
            try:
                await writer.wait_closed()
            except Exception:  # noqa: BLE001
                pass

    async def _read_greeting(self, reader: asyncio.StreamReader) -> str:
        try:
            # The marker alone can arrive before the final prompt character.
            # readuntil also preserves any following bytes for response parsing.
            async with asyncio.timeout(GREETING_TIMEOUT):
                buffer = await reader.readuntil(b":")
        except (TimeoutError, asyncio.IncompleteReadError, asyncio.LimitOverrunError) as err:
            raise NovoSysControlConnectionError(
                f"Incomplete greeting from {self.host}:{self.port}"
            ) from err

        final_text = buffer.decode("ascii", errors="replace").strip()
        
        # Controleer of de marker (in kleine letters) voorkomt in de tekst
        if GREETING_MARKER not in final_text.lower():
            raise NovoSysControlConnectionError(f"Unexpected greeting text: {final_text!r}")
            
        return final_text

    async def _read_response(self, reader: asyncio.StreamReader, *, required: bool = True) -> str:
        """Read status or acknowledgement with a total, rather than per-line, deadline."""
        try:
            async with asyncio.timeout(COMMAND_TIMEOUT):
                while True:
                    chunk = await reader.readline()
                    if not chunk:
                        break
                    line = chunk.decode("ascii", errors="replace").strip()
                    _LOGGER.debug("Raw line read from %s: %r", self.host, line)
                    if line.startswith("[") and "]" in line:
                        line = line.split("]", 1)[1].strip()
                    if not line or GREETING_MARKER in line.lower():
                        continue
                    if "received" in line.lower() and required:
                        continue
                    return line
        except TimeoutError as err:
            if required:
                raise NovoSysControlConnectionError(
                    f"Timeout waiting for status from {self.host}:{self.port}"
                ) from err
        if required:
            raise NovoSysControlConnectionError(
                f"Connection closed without status from {self.host}:{self.port}"
            )
        # SET commands are allowed to have no acknowledgement. Power commands
        # are checked separately against the actual reported power state.
        return ""

    async def set_power(self, awake: bool) -> None:
        """Set and verify power; retry once if the screen ignores the command."""
        command = "wakeup" if awake else "standby"
        last_state = "unknown"
        async with self._lock:
            for attempt in range(POWER_COMMAND_ATTEMPTS):
                await self._send_command(command)
                for _ in range(POWER_STATE_CHECKS):
                    await asyncio.sleep(POWER_CHECK_INTERVAL)
                    response, _model = await self._send_command("powerstate")
                    last_state = self._power_state(response)
                    if last_state == command:
                        return
                _LOGGER.warning(
                    "%s did not reach %s after attempt %s; reported %r",
                    self.host, command, attempt + 1, last_state,
                )
        raise NovoSysControlCommandError(
            f"{self.host} did not enter {command}; reported power state: {last_state!r}"
        )

    @staticmethod
    def _power_state(response: str) -> str:
        """Normalize plain and sentence-form power replies."""
        match = re.search(r"\b(wakeup|standby)\b", response.lower())
        return match.group(1) if match else response.lower().strip()

    @staticmethod
    def _parse_model(greeting: str) -> str | None:
        match = MODEL_RE.search(greeting)
        return match.group(1) if match else None

    async def get_status(self) -> dict:
        """Keep the entire polling session exclusive with control commands."""
        async with self._lock:
            return await self._get_status()

    async def _get_status(self) -> dict:
        """Poll status for ND-M1000 binnen één enkele TCP-sessie."""
        _LOGGER.debug("Opening single session to fetch all status parameters from %s", self.host)

        try:
            reader, writer = await asyncio.wait_for(
                asyncio.open_connection(self.host, self.port),
                timeout=CONNECT_TIMEOUT,
            )
        except (TimeoutError, OSError) as err:
            raise NovoSysControlConnectionError(f"Cannot connect to {self.host}:{self.port}") from err

        try:
            # 1. Lees de begroeting éénmalig en bepaal het model
            greeting = await self._read_greeting(reader)
            model = self._parse_model(greeting)
            _LOGGER.debug("Greeting received. Model parsed: %s", model)

            # 2. Definieer de commando's die we achter elkaar gaan sturen
            commands = ["powerstate", "sourcestate", "volstate", "mutestate", "blstate"]
            
            # Als het model nog niet bekend is uit de greeting, vragen we het direct uit
            if not model:
                commands.append("query")

            raw_responses = {}

            # 3. Stuur alle commando's over dezelfde verbinding
            for command in commands:
                payload = (command + "\n").encode("ascii")
                writer.write(payload)
                await writer.drain()

                # Lees direct het antwoord voor dit specifieke commando
                response = await self._read_response(reader)
                _LOGGER.debug("Response for %r: %r", command, response)
                raw_responses[command] = response

        except OSError as err:
            raise NovoSysControlConnectionError(f"Communication failed with {self.host}:{self.port}") from err
        finally:
            # 4. Sluit de verbinding pas als alles klaar is (of bij een fout)
            writer.close()
            try:
                await writer.wait_closed()
            except Exception:  # noqa: BLE001
                pass

        # Extracteer de waardes uit onze verzamelde data
        powerstate = raw_responses.get("powerstate", "").lower()
        sourcestate = raw_responses.get("sourcestate", "").lower()
        volstate = raw_responses.get("volstate", "").lower()
        mutestate = raw_responses.get("mutestate", "").lower()
        blstate = raw_responses.get("blstate", "").lower()
        query = raw_responses.get("query", model or "")

        # Veilig getallen filteren uit zinnen (bijv. uit "Volume is 20")
        import re
        vol_digits = re.findall(r'\d+', volstate)
        volume = int(vol_digits[0]) if vol_digits else None

        bl_digits = re.findall(r'\d+', blstate)
        backlight = int(bl_digits[0]) if bl_digits else None

        # --- EXACTE POWER STATE MAPPING VOOR JOUW INTEGRATIE ---
        if "wakeup" in powerstate:
            power_value = "wakeup"  # Voldoet aan switch.py én onze nieuwe sensor.py
        elif "standby" in powerstate:
            power_value = "standby" 
        else:
            power_value = powerstate.replace("device is", "").replace(".", "").strip()

        # --- EXACTE SOURCE MAPPING ---
        source_value = sourcestate.replace("current source is", "").replace("device is", "").replace(".", "").strip().upper()

        return {
            "model": model or query or "Vivitek ND-M1000",
            "power": power_value,       # Matcht nu met switch.py én sensor.py
            "source": source_value,     # Matcht nu met sensor.py
            "volume": volume,
            "mute": "mute" in mutestate and "unmute" not in mutestate,
            "backlight": backlight,
            "raw": raw_responses,
        }

    async def _command_with_model(self, command: str, known_model: str | None) -> tuple[str, str | None]:
        response, model = await self.send_command(command)
        return response, model or known_model
