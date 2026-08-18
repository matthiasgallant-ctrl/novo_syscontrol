from __future__ import annotations

import asyncio
import logging
import re
import time

from .const import COMMAND_TIMEOUT, CONNECT_TIMEOUT, DEFAULT_PORT, GREETING_MARKER, GREETING_TIMEOUT

_LOGGER = logging.getLogger(__name__)

MODEL_RE = re.compile(r"\[([^\]]+)\]")


class NovoSysControlError(Exception):
    """Base error."""


class NovoSysControlConnectionError(NovoSysControlError):
    """Connection or handshake failed."""


class NovoSysControlClient:
    """Async TCP client for Novo SysControl."""

    def __init__(self, host: str, port: int = DEFAULT_PORT) -> None:
        self.host = host
        self.port = port

    async def send_command(self, command: str) -> tuple[str, str | None]:
        command = command.strip()
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

            response = await self._read_response(reader)
            _LOGGER.debug("Response from %s for %r: %r", self.host, command, response)
            return response, model  # type: ignore[return-value]
        finally:
            writer.close()
            try:
                await writer.wait_closed()
            except Exception:  # noqa: BLE001
                pass

    async def _read_greeting(self, reader: asyncio.StreamReader) -> str:
        buffer = b""
        
        try:
            # We bewaken de totale tijd (5.0 seconden uit const.py)
            async with asyncio.timeout(CONNECT_TIMEOUT):
                while True:
                    chunk = await reader.read(1024)
                    if not chunk:
                        break
                        
                    buffer += chunk
                    text = buffer.decode("ascii", errors="replace").lower()
                    
                    # Stop direct zodra de marker of de dubbele punt is gevonden
                    if GREETING_MARKER in text or ":" in text:
                        break
                        
        except TimeoutError as err:
            text_err = buffer.decode("ascii", errors="replace").strip()
            raise NovoSysControlConnectionError(
                f"Timeout waiting for greeting. Received so far: {text_err!r}"
            ) from err

        final_text = buffer.decode("ascii", errors="replace").strip()
        
        # Controleer of de marker (in kleine letters) voorkomt in de tekst
        if GREETING_MARKER not in final_text.lower():
            raise NovoSysControlConnectionError(f"Unexpected greeting text: {final_text!r}")
            
        return final_text

    async def _read_response(self, reader: asyncio.StreamReader) -> str:
        """Lees het antwoord van de Vivitek en filter de statuswaarde eruit."""
        try:
            while True:
                # Lees regel voor regel
                chunk = await asyncio.wait_for(reader.readline(), timeout=COMMAND_TIMEOUT)
                if not chunk:
                    return ""

                line = chunk.decode("ascii", errors="replace").strip()
                _LOGGER.debug("Raw line read from Vivitek: %r", line)

                # Sla lege regels en de "Command ... received" regel over
                if not line or "received" in line.lower():
                    continue

                # We hebben de statusregel! Filter de prefix [ND-M1000] eruit
                if line.startswith("[") and "]" in line:
                    # Splitst op ']' en pakt het rechterdeel
                    line = line.split("]", 1)[1].strip()

                return line

        except TimeoutError:
            _LOGGER.warning("Timeout while waiting for response from Vivitek")
            return ""

    @staticmethod
    def _parse_model(greeting: str) -> str | None:
        match = MODEL_RE.search(greeting)
        return match.group(1) if match else None

    async def get_status(self) -> dict:
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