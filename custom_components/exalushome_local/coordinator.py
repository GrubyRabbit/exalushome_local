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
        """Initialize coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            name="ExalusHome Local",
            update_interval=timedelta(seconds=DEFAULT_STATE_POLLING_INTERVAL),
        )
        
        self.client = ExalusLocalClient(host, serial, pin, email, password)
        self._host = host
        self._serial = serial
        self._shutters: Dict[str, ShutterDevice] = {}
        
    async def async_config_entry_first_refresh(self) -> bool:
        """Perform first refresh on config entry setup."""
        try:
            if not await self.client.connect():
                raise UpdateFailed("Failed to connect to controller")
            
            # Register state change callback
            self.client.on_state_changed(self._on_device_state_changed)
            
            return await super().async_config_entry_first_refresh()
        except Exception as e:
            _LOGGER.error(f"First refresh failed: {e}")
            raise
    
    async def _async_update_data(self) -> Dict[str, ShutterDevice]:
        """Fetch latest data from controller."""
        try:
            if not self.client.is_connected:
                _LOGGER.warning("Not connected, attempting reconnect")
                if not await self.client.connect():
                    raise UpdateFailed("Cannot reconnect to controller")
            
            # Fetch devices from controller
            devices = await self.client.fetch_devices()
            
            # Update shutters: merge device metadata with existing websocket state
            self._update_shutters_from_devices(devices)
            
            return self._shutters
            
        except Exception as e:
            _LOGGER.error(f"Update failed: {e}")
            raise UpdateFailed(f"Failed to update: {e}")
    
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
                unique_id = f"{device_guid}_{channel}"
                
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
        
        Args:
            state_data: State change data from /info/devices/device/state/changed with DataType=BlindPosition
                Structure from library:
                - DeviceGuid: device GUID
                - DataType: "BlindPosition" (filtered by client)
                - state: object containing:
                  - Channel: channel number
                  - Position: blind position (Exalus scale)
                  - RawPosition: raw position value
                  - StateReliability: state reliability enum
                  - Time: timestamp
        """
        try:
            _LOGGER.debug(f"[STATE-COORD] Handler called with: {state_data}")
            
            device_guid = state_data.get("DeviceGuid")
            state_info = state_data.get("state", {})
            channel = state_info.get("Channel")
            position_exalus = state_info.get("Position")
            task_execution = state_data.get("TaskExecution", 0)
            
            _LOGGER.debug(
                f"[STATE-COORD] Extracted: device={device_guid}, channel={channel}, "
                f"position={position_exalus}, task_exec={task_execution}"
            )
            
            if device_guid is None or channel is None:
                _LOGGER.debug(f"[STATE-COORD] Invalid: missing DeviceGuid or Channel")
                return
            
            # Find matching shutter
            unique_id = f"{device_guid}_{channel}"
            _LOGGER.debug(f"[STATE-COORD] Shutter unique_id: {unique_id}")
            
            if unique_id not in self._shutters:
                _LOGGER.debug(f"[STATE-COORD] Shutter not found in {list(self._shutters.keys())}")
                return
            
            shutter = self._shutters[unique_id]
            old_position = shutter.current_position
            old_moving = shutter.is_moving
            
            _LOGGER.debug(f"[STATE-COORD] Shutter found: old_pos={old_position}, old_moving={old_moving}")
            
            # Update position if provided (convert from Exalus to HA scale)
            if position_exalus is not None:
                shutter.current_position = exalus_to_ha_position(position_exalus)
                _LOGGER.debug(
                    f"[STATE-COORD] Position updated: Exalus={position_exalus} → HA={shutter.current_position}"
                )
            else:
                _LOGGER.debug(f"[STATE-COORD] Position=None, not updating")
            
            # Update moving state
            shutter.is_moving = task_execution != 0
            
            _LOGGER.debug(
                f"[STATE-COORD] Final state: pos={shutter.current_position}, "
                f"moving={shutter.is_moving}, changed={old_position != shutter.current_position or old_moving != shutter.is_moving}"
            )
            
            # Trigger coordinator update to notify entities
            self.async_set_updated_data(self._shutters)
            _LOGGER.debug(f"[STATE-COORD] Coordinator updated")
            
        except Exception as e:
            _LOGGER.error(f"[STATE-COORD] Error: {e}", exc_info=True)
    
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
