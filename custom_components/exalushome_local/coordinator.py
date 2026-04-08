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
            # TODO: Implement actual device fetch from local API
            devices = await self.client.fetch_devices()
            
            # Filter and map shutters
            shutters = self._extract_shutters(devices)
            self._shutters = shutters
            
            return shutters
            
        except Exception as e:
            _LOGGER.error(f"Update failed: {e}")
            raise UpdateFailed(f"Failed to update: {e}")
    
    def _extract_shutters(self, devices: Dict[str, Device]) -> Dict[str, ShutterDevice]:
        """Extract shutter devices from device list.
        
        Args:
            devices: Dictionary of devices
        
        Returns:
            Dictionary of shutter devices mapped by unique ID
        """
        shutters = {}
        
        for device_guid, device in devices.items():
            if not device.available:
                continue
            
            # Get blind channels from device
            blind_channels = device.get_blind_channels()
            
            for channel in blind_channels:
                shutter = ShutterDevice(
                    device_guid=device_guid,
                    device_name=device.name,
                    channel=channel,
                )
                shutters[shutter.unique_id] = shutter
        
        return shutters
    
    async def _on_device_state_changed(self, state_data: Dict):
        """Handle device state changed event from WebSocket.
        
        Args:
            state_data: State change data from /info/devices/device/state/changed event
                - DeviceGuid: device GUID
                - Channel: channel number
                - state.Position: Exalus position (0=open, 100=closed)
                - state.TaskExecution: task execution state (0=idle, 1=executing)
        """
        try:
            # Debug: log raw event
            _LOGGER.debug(f"Raw state event: {state_data}")
            
            device_guid = state_data.get("DeviceGuid")
            channel = state_data.get("Channel")
            state_info = state_data.get("state", {})
            position_exalus = state_info.get("Position")
            task_execution = state_info.get("TaskExecution", 0)
            
            if device_guid is None or channel is None:
                _LOGGER.debug("Invalid state data: missing DeviceGuid or Channel")
                return
            
            # Find matching shutter
            unique_id = f"{device_guid}_{channel}"
            if unique_id not in self._shutters:
                _LOGGER.debug(f"Unknown shutter: {unique_id}")
                return
            
            shutter = self._shutters[unique_id]
            old_position = shutter.current_position
            old_moving = shutter.is_moving
            
            # Update position if provided (convert from Exalus to HA scale)
            # Exalus: 0=open, 100=closed
            # HA: 100=open, 0=closed
            if position_exalus is not None:
                shutter.current_position = exalus_to_ha_position(position_exalus)
                _LOGGER.debug(
                    f"Position update: Exalus={position_exalus} → HA={shutter.current_position}"
                )
            
            # Update moving state (0=idle/stopped, 1=executing/moving)
            shutter.is_moving = task_execution != 0
            
            _LOGGER.debug(
                f"State updated {unique_id}: "
                f"position {old_position}→{shutter.current_position}, "
                f"moving {old_moving}→{shutter.is_moving}, "
                f"TaskExecution={task_execution}"
            )
            
            # Trigger coordinator update to notify entities
            self.async_set_updated_data(self._shutters)
            
        except Exception as e:
            _LOGGER.error(f"Error processing state change: {e}")
    
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
