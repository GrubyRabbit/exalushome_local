"""Cover entities for ExalusHome Local shutters."""

import logging
from typing import Any, Dict, Optional

from homeassistant.components.cover import (
    CoverEntity,
    CoverEntityFeature,
    CoverDeviceClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .coordinator import ExalusHomeLocalCoordinator
from .api.models import ShutterDevice
from .const import (
    DOMAIN,
    BLIND_CONTROL_OPEN,
    BLIND_CONTROL_CLOSE,
    BLIND_CONTROL_STOP,
    exalus_to_ha_position,
    ha_to_exalus_position,
)

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up cover entities from config entry."""
    host = config_entry.data.get("host")
    serial = config_entry.data.get("serial")
    pin = config_entry.data.get("pin")
    
    # Create coordinator
    coordinator = ExalusHomeLocalCoordinator(hass, host, serial, pin)
    await coordinator.async_config_entry_first_refresh()
    
    # Store coordinator in hass data
    if DOMAIN not in hass.data:
        hass.data[DOMAIN] = {}
    hass.data[DOMAIN][config_entry.entry_id] = coordinator
    
    # Create cover entities for all shutters
    entities = []
    for unique_id, shutter in coordinator.data.items():
        entity = ExalusHomeShutterCover(coordinator, shutter)
        entities.append(entity)
    
    async_add_entities(entities)


class ExalusHomeShutterCover(CoordinatorEntity, CoverEntity):
    """Representation of an ExalusHome shutter."""
    
    def __init__(self, coordinator: ExalusHomeLocalCoordinator, shutter: ShutterDevice):
        """Initialize cover entity."""
        super().__init__(coordinator)
        self._shutter = shutter
        
        # Set device class to shutter
        self._attr_device_class = CoverDeviceClass.SHUTTER
        
        # Support open, close, and stop
        self._attr_supported_features = (
            CoverEntityFeature.OPEN
            | CoverEntityFeature.CLOSE
            | CoverEntityFeature.STOP
            | CoverEntityFeature.SET_POSITION
        )
    
    @property
    def unique_id(self) -> str:
        """Return unique ID for entity."""
        return f"exalushome_local_{self._shutter.unique_id}"
    
    @property
    def name(self) -> str:
        """Return name of the cover."""
        return self._shutter.name
    
    @property
    def current_cover_position(self) -> Optional[int]:
        """Return current position (0-100, HA scale: 0=closed, 100=open)."""
        if self._shutter.available:
            return self._shutter.current_position
        return None
    
    @property
    def is_closed(self) -> Optional[bool]:
        """Return whether cover is closed.
        
        In HA: position 0 = closed
        In Exalus: position 100 = closed
        So is_closed = (position == 0)
        """
        if not self._shutter.available:
            return None
        return self._shutter.current_position == 0
    
    @property
    def is_closing(self) -> bool:
        """Return whether cover is closing."""
        # TODO: Implement based on state tracking
        # Currently cannot distinguish close from open movement
        return False
    
    @property
    def is_opening(self) -> bool:
        """Return whether cover is opening."""
        # For now, if moving and not closing, assume opening
        # TODO: Implement proper direction tracking
        return self._shutter.is_moving
    
    @property
    def available(self) -> bool:
        """Return whether cover is available."""
        return self._shutter.available
    
    async def async_open_cover(self, **kwargs: Any) -> None:
        """Open the cover."""
        _LOGGER.debug(f"Opening {self._shutter.unique_id}")
        
        # Send open command (101)
        success = await self.coordinator.send_command(
            self._shutter.device_guid,
            self._shutter.channel.number,
            BLIND_CONTROL_OPEN,
        )
        
        if success:
            # Update local state immediately (optimistic)
            self._shutter.current_position = 100  # HA scale: 100 = open
            self._shutter.is_moving = True
            self.async_write_ha_state()
        else:
            _LOGGER.error(f"Failed to open {self._shutter.unique_id}")
    
    async def async_close_cover(self, **kwargs: Any) -> None:
        """Close the cover."""
        _LOGGER.debug(f"Closing {self._shutter.unique_id}")
        
        # Send close command (102)
        success = await self.coordinator.send_command(
            self._shutter.device_guid,
            self._shutter.channel.number,
            BLIND_CONTROL_CLOSE,
        )
        
        if success:
            # Update local state immediately (optimistic)
            self._shutter.current_position = 0  # HA scale: 0 = closed
            self._shutter.is_moving = True
            self.async_write_ha_state()
        else:
            _LOGGER.error(f"Failed to close {self._shutter.unique_id}")
    
    async def async_stop_cover(self, **kwargs: Any) -> None:
        """Stop the cover."""
        _LOGGER.debug(f"Stopping {self._shutter.unique_id}")
        
        # Send stop command (103)
        success = await self.coordinator.send_command(
            self._shutter.device_guid,
            self._shutter.channel.number,
            BLIND_CONTROL_STOP,
        )
        
        if success:
            self._shutter.is_moving = False
            self.async_write_ha_state()
        else:
            _LOGGER.error(f"Failed to stop {self._shutter.unique_id}")
    
    async def async_set_cover_position(self, **kwargs: Any) -> None:
        """Set cover position (0-100, HA scale)."""
        position_ha = kwargs.get("position")
        
        if position_ha is None:
            _LOGGER.error("No position provided")
            return
        
        # Convert HA position to Exalus position
        position_exalus = ha_to_exalus_position(int(position_ha))
        
        _LOGGER.debug(
            f"Setting {self._shutter.unique_id} to position {position_ha} "
            f"(Exalus: {position_exalus})"
        )
        
        # Send set position command
        success = await self.coordinator.send_command(
            self._shutter.device_guid,
            self._shutter.channel.number,
            position_exalus,
        )
        
        if success:
            # Update local state immediately (optimistic)
            self._shutter.current_position = position_ha
            self._shutter.is_moving = True
            self.async_write_ha_state()
        else:
            _LOGGER.error(f"Failed to set position for {self._shutter.unique_id}")
