"""Button entities for ExalusHome Local shutters."""

import logging
from typing import Any

from homeassistant.components.button import ButtonEntity
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .coordinator import ExalusHomeLocalCoordinator
from .api.models import ShutterDevice
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up microventilation button entities from config entry."""
    coordinator = hass.data[DOMAIN][config_entry.entry_id]

    entities = [
        ExalusHomeShutterMicroventilationButton(coordinator, shutter)
        for shutter in coordinator.data.values()
        if shutter.supports_microventilation
    ]

    async_add_entities(entities)


class ExalusHomeShutterMicroventilationButton(CoordinatorEntity, ButtonEntity):
    """Producer-aligned microventilation trigger for an ExalusHome shutter."""

    _attr_has_entity_name = True
    _attr_icon = "mdi:window-shutter-alert"

    def __init__(self, coordinator: ExalusHomeLocalCoordinator, shutter: ShutterDevice):
        """Initialize button entity."""
        super().__init__(coordinator)
        self._shutter = shutter

    @property
    def unique_id(self) -> str:
        """Return unique ID for entity."""
        return f"exalushome_local_{self._shutter.unique_id}_microventilation"

    @property
    def device_info(self) -> DeviceInfo:
        """Group under the same device as the cover entity for this shutter."""
        return DeviceInfo(
            identifiers={(DOMAIN, self._shutter.unique_id)},
            name=self._shutter.name,
        )

    @property
    def name(self) -> str:
        """Return the entity-name suffix; combined with device name by HA."""
        return "Mikrowentylacja"

    @property
    def available(self) -> bool:
        """Return whether the button is available."""
        return self._shutter.available

    async def async_press(self, **kwargs: Any) -> None:
        """Send the producer-captured microventilation command."""
        _LOGGER.debug(f"Microventilation {self._shutter.unique_id}")
        success = await self.coordinator.send_microventilation(
            self._shutter.device_guid,
            self._shutter.channel.number,
        )
        if not success:
            _LOGGER.error(f"Failed to trigger microventilation for {self._shutter.unique_id}")
