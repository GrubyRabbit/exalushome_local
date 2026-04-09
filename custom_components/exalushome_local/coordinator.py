"""Coordinator for ExalusHome Local integration."""

import asyncio
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
from .const import DEFAULT_STATE_POLLING_INTERVAL, exalus_to_ha_position, CONF_EMAIL, CONF_PASSWORD

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
        self._stop_timers: Dict[str, asyncio.TimerHandle] = {}  # uid -> pending stop timer
        
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
    
    
    # Inactivity window: if no BlindPosition event arrives within this many seconds,
    # the shutter is considered stopped. Runtime evidence shows tasks=[] and StateReliability
    # are both unreliable for stop detection on this controller.
    _POSITION_INACTIVITY_STOP_SECONDS = 2.0

    async def _on_device_state_changed(self, state_data: Dict):
        """Handle device state changed event from WebSocket.

        Position updates come from BlindPosition events.
        Stop detection uses per-shutter inactivity timer: if no new position event
        arrives within _POSITION_INACTIVITY_STOP_SECONDS, the shutter is stopped.
        """
        try:
            device_guid = state_data.get("DeviceGuid")
            state_info = state_data.get("state", {})
            channel = state_info.get("Channel")
            position_exalus = state_info.get("Position")
            state_reliability = state_info.get("StateReliability")

            _LOGGER.debug(f"[STATE-COORD] DeviceGuid={device_guid}, Channel={channel}, Position={position_exalus}, StateReliability={state_reliability}")

            if device_guid is None or channel is None:
                _LOGGER.debug(f"[STATE-COORD] SKIP: missing DeviceGuid or Channel")
                return

            unique_id = f"{device_guid}_{channel}"
            if unique_id not in self._shutters:
                _LOGGER.debug(f"[STATE-COORD] SKIP: Shutter {unique_id} not found")
                return

            shutter = self._shutters[unique_id]

            # Update position
            if position_exalus is not None:
                shutter.current_position = exalus_to_ha_position(position_exalus)
                if shutter.is_moving:
                    _LOGGER.debug(
                        f"[LIVE-POS] intermediate position event: "
                        f"shutter={unique_id}, Exalus={position_exalus} → HA={shutter.current_position}"
                    )
                else:
                    _LOGGER.debug(
                        f"[LIVE-POS] final position event: "
                        f"shutter={unique_id}, Exalus={position_exalus} → HA={shutter.current_position}"
                    )

            # Per-shutter inactivity stop timer:
            # Every BlindPosition event cancels and restarts the timer.
            # When the timer fires without a new event, movement has stopped.
            if unique_id in self._stop_timers:
                self._stop_timers[unique_id].cancel()

            def _inactivity_stop(u=unique_id):
                self._stop_timers.pop(u, None)
                s = self._shutters.get(u)
                if s and s.is_moving:
                    _LOGGER.debug(f"[LIVE] stop detected from BlindPosition inactivity: {u}")
                    s.is_moving = False
                    self.async_set_updated_data(self._shutters)

            self._stop_timers[unique_id] = self.hass.loop.call_later(
                self._POSITION_INACTIVITY_STOP_SECONDS, _inactivity_stop
            )
            _LOGGER.debug(
                f"[LIVE] inactivity stop timer reset for {unique_id} "
                f"(fires in {self._POSITION_INACTIVITY_STOP_SECONDS}s)"
            )

            self.async_set_updated_data(self._shutters)

        except Exception as e:
            _LOGGER.error(f"[STATE-COORD] Error: {e}", exc_info=True)
    
    async def _on_device_tasks_changed(self, tasks_data: list):
        """Handle device tasks changed event from WebSocket.

        Used ONLY to detect start of movement (non-empty tasks => is_moving=True).
        Stop detection is handled exclusively by BlindPosition inactivity timer.
        tasks=[] is ignored — it is unreliable even with debounce on this controller.
        """
        try:
            _LOGGER.debug(f"[LIVE] task event received: {tasks_data}")

            if not tasks_data:
                _LOGGER.debug(f"[LIVE] task event empty — ignored (stop detection uses inactivity timer)")
                return

            # Parse executing tasks — split on ";" and take first two non-empty tokens
            # Runtime format: "bfacc80a-8549-432e-9165-0cf75e8b9a4a;1;" (trailing semicolon)
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
                            _LOGGER.debug(f"[LIVE] channel=0 expansion: marking {uid} as executing")
                else:
                    executing.add(f"{guid}_{channel}")

            if not executing:
                return

            _LOGGER.debug(f"[LIVE] movement updated: executing={executing}")
            changed = False
            for uid in executing:
                if uid in self._shutters and not self._shutters[uid].is_moving:
                    self._shutters[uid].is_moving = True
                    changed = True
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
    
    async def async_shutdown(self):
        """Shutdown coordinator."""
        await self.client.disconnect()
