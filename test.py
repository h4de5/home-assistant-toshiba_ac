import asyncio
import json
import logging
import os
import random
import sys
from rich import print_json


sys.path.insert(1, "custom_components/toshiba_ac")

from toshiba_ac.device_manager import ToshibaAcDeviceManager
from toshiba_ac.utils.http_api import ToshibaAcHttpApiAuthError, ToshibaAcHttpApiError

if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
_LOOP = asyncio.new_event_loop()
asyncio.set_event_loop(_LOOP)

CONNECTION_TIMEOUT = 5


class ToshibaClient:
    def __init__(self, username: str, password: str, device_id: str | None = None, sas_token: str | None = None):
        self._username = username
        self._password = password
        self._device_id = device_id if device_id else f"{random.getrandbits(64):016x}"
        self._sas_token = sas_token
        self._device_manager: ToshibaAcDeviceManager | None = None

    async def get_token(self):
        self._device_manager = ToshibaAcDeviceManager(username, password, device_id)
        try:
            self._sas_token = await self._device_manager.connect()
            self._device_manager.on_sas_token_updated_callback.add(self._sas_token_updated)
        except ToshibaAcHttpApiAuthError as ex:
            _LOGGER.error("Toshiba connection error %s", ex)
        except ToshibaAcHttpApiError as ex:
            _LOGGER.error("Toshiba connection error %s", ex)
        finally:
            _LOGGER.error("Toshiba connection OK")
            await self._device_manager.shutdown()
        _LOGGER.debug("Device Id=%s", self._device_id)
        _LOGGER.debug("Token=%s", self._sas_token)

    async def _sas_token_updated(self, new_sas_token: str) -> None:
        """Handle SAS token update from the device manager."""
        _LOGGER.info("SAS token updated by device manager: %s", new_sas_token)
        self._sas_token = new_sas_token

    async def check_connection(self) -> bool:
        try:
            connection_ok = True
            # Check AMQP connection (Azure IoT Hub)
            if self._device_manager.amqp_api and self._device_manager.amqp_api.device:
                # The Azure IoT Hub client has a connected property
                if hasattr(self._device_manager.amqp_api.device, "connected"):
                    if not self._device_manager.amqp_api.device.connected:
                        _LOGGER.warning("Azure IoT Hub connection lost")
                        connection_ok = False
            elif not self._device_manager.amqp_api:
                # AMQP API not initialized
                _LOGGER.warning("AMQP API not initialized")
                connection_ok = False

            # Check HTTP API
            if not self._device_manager.http_api:
                _LOGGER.warning("HTTP API not initialized")
                connection_ok = False

            if not connection_ok:
                _LOGGER.info("Connection health check failed, attempting reconnect...")
                await self._attempt_reconnect()
            return connection_ok
        except Exception as ex:
            _LOGGER.debug("Connection health check error: %s", ex)
            # If we can't even check, the connection is likely dead
            await self._attempt_reconnect()
            return False

    async def _attempt_reconnect(self):
        try:
            # Shutdown existing connection gracefully
            try:
                await asyncio.wait_for(self._device_manager.shutdown(), timeout=10)
            except asyncio.TimeoutError:
                _LOGGER.debug("Shutdown timed out, forcing cleanup")
            except Exception as ex:
                _LOGGER.debug("Error during shutdown before reconnect: %s", ex)

            # Reset internal state
            self._device_manager.http_api = None
            self._device_manager.amqp_api = None
            self._device_manager.devices = {}

            # Reconnect with timeout
            new_sas_token = await asyncio.wait_for(self._device_manager.connect(), timeout=CONNECTION_TIMEOUT)

            if new_sas_token and new_sas_token != self._sas_token:
                _LOGGER.info("SAS token updated during reconnection : %s", new_sas_token)
                self._sas_token = new_sas_token

            # Re-fetch devices to restore state
            await asyncio.wait_for(self._device_manager.get_devices(), timeout=CONNECTION_TIMEOUT)

            _LOGGER.info("Successfully reconnected to Toshiba AC cloud")
        except asyncio.TimeoutError:
            _LOGGER.warning("Reconnection attempt timed out")
        except Exception as ex:
            _LOGGER.warning("Reconnection attempt failed: %s", ex)

    async def connect(self):
        self._device_manager = ToshibaAcDeviceManager(self._username, self._password, self._device_id, self._sas_token)
        try:
            # Wrap connect() with a timeout to prevent indefinite hangs
            new_sas_token = await asyncio.wait_for(self._device_manager.connect(), timeout=CONNECTION_TIMEOUT)
            # Save updated SAS token if we got a new one
            if new_sas_token and new_sas_token != self._sas_token:
                self._sas_token = new_sas_token
                _LOGGER.info("SAS token updated during connection: %s", new_sas_token)
            _LOGGER.debug("Connection status: %s", await self.check_connection())
        except asyncio.TimeoutError:
            _LOGGER.warning("Connection to Toshiba AC cloud timed out after %d seconds", CONNECTION_TIMEOUT)
            # Clean up partial state
            try:
                await self._device_manager.shutdown()
            except Exception:
                pass

        except Exception as ex:
            error_str = str(ex).lower()
            # Check for authentication-related errors
            if "401" in error_str or "403" in error_str or "auth" in error_str:
                _LOGGER.error("Authentication failed. Please reconfigure the integration. %s", ex)
            else:
                _LOGGER.error("Failed to connect t failed. Please reconfigure the integration. %s", ex)

    async def get_data(self):
        _LOGGER.debug("Extracting devices data")
        devices = await self._device_manager.get_devices()
        data = []
        for device in devices:
            data.append({"device_id": device.device_id, "name": device.name, "mode": str(device.ac_mode)})
        print_json(data=data)


async def main():
    # JSON config file with fields : username, password, token (optional), device_id (optional)
    with open("config.json") as json_data:
        data = json.load(json_data)
        json_data.close()
        username = data["username"]
        password = data["password"]
        token = data.get("token", None)
        device_id = data.get("device_id", None)
    client = ToshibaClient(username=username, password=password, device_id=device_id, sas_token=token)
    await client.connect()
    await client.get_data()


if __name__ == "__main__":
    _LOGGER = logging.getLogger(__name__)
    formatter = logging.Formatter("%(asctime)s %(levelname)s %(message)s")
    ch = logging.StreamHandler()
    ch.setFormatter(formatter)
    logging.basicConfig(handlers=[ch])
    logging.getLogger(__name__).setLevel(logging.DEBUG)
    logging.getLogger("toshiba_ac").setLevel(logging.DEBUG)
    _LOOP.run_until_complete(main())
    _LOOP.run_forever()
