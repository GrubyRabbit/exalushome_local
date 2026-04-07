"""ExalusHome Local integration for Home Assistant."""

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import DOMAIN, CONF_EMAIL, CONF_PASSWORD

PLATFORMS = ["cover"]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up ExalusHome Local from a config entry."""
    hass.data.setdefault(DOMAIN, {})
    
    # Store entry config for use by platforms
    hass.data[DOMAIN][entry.entry_id] = {
        "host": entry.data.get("host"),
        "serial": entry.data.get("serial"),
        "pin": entry.data.get("pin"),
        "email": entry.data.get("email"),
        "password": entry.data.get("password"),
    }
    
    # Forward setup to platforms
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    # Unload platforms
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id, None)
    
    return unload_ok
