"""Coordinator for ExalusHome Local integration."""

import logging
from datetime import timedelta
from typing import Dict, List, Optional

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
    UpdateFailed,
)

from .api.client import ExalusLocalClient
from .api.models import Device, DeviceChannel, ShutterDevice, ControlFeature, DeviceState
from .const import DEFAULT_STATE_POLLING_INTERVAL, exalus_to_ha_position, CONF_EMAIL, CONF_PASSWORD, BLIND_MICROVENTILATION_DATA

_LOGGER = logging.getLogger(__name__)


class ExalusHomeLocalCoordinator(DataUpdateCoordinator):
    """Coordinator for ExalusHome Local data updates."""
    
    def __init__(
        self,
        hass: HomeAssistant,
        host: str,
        serial: str,
        pin: str,
        email: str = None,
        password: str = None,
    ):
        """Initialize coordinator.
        
        Periodic /devices/list polling is disabled.
        Device enumeration happens only on:
        - initial startup (async_config_entry_first_refresh)
        - websocket reconnect
        
        Websocket state events provide live blind state updates.
        """
        super().__init__(
            hass,
            _LOGGER,
            name="ExalusHome Local",
            update_interval=None,  # No periodic polling; websocket provides live state
        )
        
        self.client = ExalusLocalClient(host, serial, pin, email, password)
        self._host = host
        self._serial = serial
        self._shutters: Dict[str, ShutterDevice] = {}
        self._startup_complete = False
        
    async def async_config_entry_first_refresh(self) -> bool:
        """Perform first refresh on config entry setup."""
        try:
            if not await self.client.connect():
                raise UpdateFailed("Failed to connect to controller")
            
            # Register state change callback
            self.client.on_state_changed(self._on_device_state_changed)
            
            # Register tasks changed callback (source of truth for movement state)
            self.client.on_task_changed(self._on_device_tasks_changed)
            
            # Register logout callback for session recovery
            self.client.on_logout(self._on_session_logout)
            
            _LOGGER.debug(f"[REFRESH] Startup refresh beginning")
            result = await super().async_config_entry_first_refresh()
            self._startup_complete = True
            _LOGGER.debug(f"[REFRESH] Startup refresh complete")
            return result
        except Exception as e:
            _LOGGER.error(f"First refresh failed: {e}")
            raise
    
    async def async_refresh(self, log_failures: bool = True, force_refresh: bool = False):
        """Override to prevent automatic refreshes after startup.
        
        Device enumeration only happens on:
        - startup (via async_config_entry_first_refresh)
        - websocket reconnect (explicit call with force_refresh=True)
        """
        if not force_refresh and self._startup_complete:
            _LOGGER.debug(f"[REFRESH] Blocked automatic refresh request - using cached state")
            return
        
        _LOGGER.debug(f"[REFRESH] Allowed refresh: force_refresh={force_refresh}, startup_complete={self._startup_complete}")
        await super().async_refresh(log_failures=log_failures, force_refresh=force_refresh)
    
    async def _async_update_data(self) -> Dict[str, ShutterDevice]:
        """Fetch latest data from controller.
        
        On timeout or failure, preserve existing shutters and their websocket-updated state.
        Websocket state events are the live source of truth; device refresh is metadata-only.
        """
        try:
            if not self.client.is_connected:
                _LOGGER.warning("[REFRESH] Not connected, attempting reconnect")
                if not await self.client.connect():
                    raise UpdateFailed("Cannot reconnect to controller")
            
            # Fetch devices from controller
            _LOGGER.debug(f"[REFRESH] Fetching devices from /devices/list")
            devices = await self.client.fetch_devices()
            
            # Update shutters: merge device metadata with existing websocket state
            self._update_shutters_from_devices(devices)
            
            return self._shutters
            
        except Exception as e:
            # Timeout or fetch failure: preserve existing shutters and their state
            # Websocket state updates are live and should be preserved
            _LOGGER.warning(f"[REFRESH] Device refresh failed (preserving existing {len(self._shutters)} shutters): {e}")
            if self._shutters:
                _LOGGER.debug(f"[REFRESH] Returning cached shutters: {list(self._shutters.keys())}")
                return self._shutters
            raise UpdateFailed(f"Failed to fetch devices and no cached shutters available: {e}")
    
    def _update_shutters_from_devices(self, devices: Dict[str, Device]):
        """Update shutters from device list, preserving websocket state.
        
        Merges device metadata into existing shutter objects.
        Websocket state (position, moving) is preserved.
        New shutters are added, unavailable ones are removed.
        """
        updated_shutters = {}
        
        for device_guid, device in devices.items():
            if not device.available:
                continue
            
            # Get blind channels from device
            blind_channels = device.get_blind_channels()
            
            for channel in blind_channels:
                unique_id = f"{device_guid}_{channel.number}"
                
                if unique_id in self._shutters:
                    # Existing shutter: keep websocket-updated state, update metadata
                    shutter = self._shutters[unique_id]
                    shutter.device_name = device.name
                    shutter.channel = channel
                    _LOGGER.debug(f"[UPDATE] Merged shutter {unique_id}: name={device.name}, channel={channel.number}")
                else:
                    # New shutter: create fresh
                    shutter = ShutterDevice(
                        device_guid=device_guid,
                        device_name=device.name,
                        channel=channel,
                    )
                    _LOGGER.debug(f"[UPDATE] New shutter {unique_id}: {device.name} ch{channel.number}")
                
                updated_shutters[unique_id] = shutter
        
        # Remove any shutters no longer in device list
        removed = set(self._shutters.keys()) - set(updated_shutters.keys())
        if removed:
            _LOGGER.debug(f"[UPDATE] Removed shutters: {removed}")
        
        self._shutters = updated_shutters
        _LOGGER.debug(f"[UPDATE] Shutters after merge: {len(self._shutters)} total")
    

    async def _on_device_state_changed(self, state_data: Dict):
        """Handle device state changed event from WebSocket.

        Updates shutter position from BlindPosition events.
        No stop detection here — movement state is set by /info/devices/tasks.
        """
        try:
            device_guid = state_data.get("DeviceGuid")
            state_info = state_data.get("state", {})
            channel = state_info.get("Channel")
            position_exalus = state_info.get("Position")

            _LOGGER.debug(f"[STATE-COORD] DeviceGuid={device_guid}, Channel={channel}, Position={position_exalus}")

            if device_guid is None or channel is None:
                _LOGGER.debug(f"[STATE-COORD] SKIP: missing DeviceGuid or Channel")
                return

            unique_id = f"{device_guid}_{channel}"
            if unique_id not in self._shutters:
                _LOGGER.debug(f"[STATE-COORD] SKIP: Shutter {unique_id} not found")
                return

            shutter = self._shutters[unique_id]

            if position_exalus is not None:
                shutter.current_position = exalus_to_ha_position(position_exalus)
                _LOGGER.debug(
                    f"[LIVE-POS] position updated: shutter={unique_id}, "
                    f"Exalus={position_exalus} → HA={shutter.current_position}, moving={shutter.is_moving}"
                )

            self.async_set_updated_data(self._shutters)

        except Exception as e:
            _LOGGER.error(f"[STATE-COORD] Error: {e}", exc_info=True)
    
    async def _on_device_tasks_changed(self, tasks_data: list):
        """Handle device tasks changed event from WebSocket.

        Directly mirrors official library DeviceChannel._onTasksExecutionChangedEvent:
        - Non-empty list: shutters in the list are executing => is_moving=True
        - Empty list []: no tasks executing => is_moving=False for all moving shutters
        """
        try:
            _LOGGER.debug(f"[LIVE] task event received: {tasks_data}")

            executing = set()
            for entry in tasks_data:
                tokens = [t.strip() for t in str(entry).split(";") if t.strip()]
                if len(tokens) < 2:
                    _LOGGER.debug(f"[LIVE] Could not parse task entry (expected guid;channel): {entry!r}")
                    continue
                guid = tokens[0]
                try:
                    channel = int(tokens[1])
                except ValueError:
                    _LOGGER.debug(f"[LIVE] Could not parse channel from task entry: {entry!r}")
                    continue
                if channel == 0:
                    for uid in self._shutters:
                        if uid.startswith(f"{guid}_"):
                            executing.add(uid)
                else:
                    executing.add(f"{guid}_{channel}")

            changed = False
            for uid, shutter in self._shutters.items():
                new_moving = uid in executing
                if shutter.is_moving != new_moving:
                    shutter.is_moving = new_moving
                    changed = True
                    _LOGGER.debug(f"[LIVE] {'movement start' if new_moving else 'movement stop'}: {uid}")

            if changed:
                self.async_set_updated_data(self._shutters)

        except Exception as e:
            _LOGGER.error(f"[LIVE] Error handling tasks event: {e}", exc_info=True)
    
    async def _on_session_logout(self):
        """Handle session logout event (producer-aligned).
        
        When /info/users/user/loggedOut is received:
        - Mark session as invalid
        - Log the event
        - Do NOT immediately force reconnect
        - Producer behavior: let next API call trigger restore if needed
        - Preserve existing shutters and state
        """
        try:
            _LOGGER.debug(f"[SESSION] loggedOut received - session marked invalid")
            _LOGGER.debug(f"[SESSION] Next API request will trigger session restore if needed")
            
        except Exception as e:
            _LOGGER.error(f"[SESSION] Error handling logout: {e}", exc_info=True)
    
    async def send_command(
        self,
        device_guid: str,
        channel_number: int,
        command: int,
    ) -> bool:
        """Send command to device."""
        return await self.client.send_command(device_guid, channel_number, command)

    async def send_microventilation(self, device_guid: str, channel_number: int) -> bool:
        """Trigger producer-captured microventilation (ControlFeature=13, Data=91)."""
        return await self.client.send_command(
            device_guid,
            channel_number,
            BLIND_MICROVENTILATION_DATA,
            control_feature=ControlFeature.Microventilation,
        )

    async def async_shutdown(self):
        """Shutdown coordinator."""
        await self.client.disconnect()
