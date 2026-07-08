"""ExalusHome Local integration for Home Assistant."""

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .coordinator import ExalusHomeLocalCoordinator
from .const import DOMAIN, CONF_EMAIL, CONF_PASSWORD

PLATFORMS = ["cover", "button"]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up ExalusHome Local from a config entry."""
    hass.data.setdefault(DOMAIN, {})

    # Create the single shared coordinator (owns the websocket connection)
    # before forwarding to platforms, so no platform ever creates its own.
    coordinator = ExalusHomeLocalCoordinator(
        hass,
        entry.data.get("host"),
        entry.data.get("serial"),
        entry.data.get("pin"),
        entry.data.get("email"),
        entry.data.get("password"),
    )
    await coordinator.async_config_entry_first_refresh()
    hass.data[DOMAIN][entry.entry_id] = coordinator

    # Forward setup to platforms
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    # Unload platforms
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)

    if unload_ok:
        coordinator = hass.data[DOMAIN].get(entry.entry_id)
        if coordinator is not None:
            await coordinator.async_shutdown()
        hass.data[DOMAIN].pop(entry.entry_id, None)

    return unload_ok
