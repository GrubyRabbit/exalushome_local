"""Config flow for ExalusHome Local."""

from typing import Any, Dict, Optional
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResult

from .const import DOMAIN, CONF_HOST, CONF_SERIAL, CONF_PIN
from .api.client import ExalusLocalClient

import logging
_LOGGER = logging.getLogger(__name__)


class ExalusHomeLocalConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Config flow for ExalusHome Local."""
    
    VERSION = 1
    
    async def async_step_user(
        self, user_input: Optional[Dict[str, Any]] = None
    ) -> FlowResult:
        """Handle user-initiated config flow."""
        errors = {}
        
        if user_input is not None:
            # Validate and normalize input
            try:
                # Normalize host - strip protocols and slashes
                host = user_input.get(CONF_HOST, "").strip()
                host = self._normalize_host(host)
                
                serial = user_input.get(CONF_SERIAL, "").strip()
                pin = user_input.get(CONF_PIN, "").strip()
                
                if not host or not serial or not pin:
                    errors["base"] = "invalid_input"
                elif "/" in host or "://" in host:
                    # User provided protocol or path - normalize didn't catch it
                    errors[CONF_HOST] = "invalid_host"
                else:
                    # Test connection with normalized host
                    client = ExalusLocalClient(host, serial, pin)
                    if await client.connect():
                        await client.disconnect()
                        
                        # Check for duplicate entries
                        await self.async_set_unique_id(serial)
                        self._abort_if_unique_id_configured()
                        
                        # Store normalized host in config
                        config_data = dict(user_input)
                        config_data[CONF_HOST] = host
                        
                        return self.async_create_entry(
                            title=f"ExalusHome {host}",
                            data=config_data,
                        )
                    else:
                        errors["base"] = "cannot_connect"
            except Exception as e:
                _LOGGER.error(f"Config flow error: {e}")
                errors["base"] = "unknown_error"
        
        # Show form
        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema({
                vol.Required(CONF_HOST): str,
                vol.Required(CONF_SERIAL): str,
                vol.Required(CONF_PIN): str,
            }),
            errors=errors,
            description_placeholders={},
        )
    
    @staticmethod
    def _normalize_host(host: str) -> str:
        """Normalize host by removing protocol prefixes and trailing slashes.
        
        Args:
            host: Raw host input (may contain protocols like http://, ws://, etc.)
            
        Returns:
            Normalized host/IP address
        """
        host = host.strip()
        
        # Remove protocol prefixes
        for prefix in ("wss://", "ws://", "https://", "http://"):
            if host.lower().startswith(prefix):
                host = host[len(prefix):]
        
        # Remove trailing slashes and paths
        host = host.rstrip("/").split("/")[0]
        
        return host


config_entries.HANDLERS.register(ExalusHomeLocalConfigFlow)
