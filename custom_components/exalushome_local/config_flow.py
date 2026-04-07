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
            # Validate input
            try:
                host = user_input.get(CONF_HOST, "").strip()
                serial = user_input.get(CONF_SERIAL, "").strip()
                pin = user_input.get(CONF_PIN, "").strip()
                
                if not host or not serial or not pin:
                    errors["base"] = "invalid_input"
                else:
                    # Test connection
                    client = ExalusLocalClient(host, serial, pin)
                    if await client.connect():
                        await client.disconnect()
                        
                        # Check for duplicate entries
                        await self.async_set_unique_id(serial)
                        self._abort_if_unique_id_configured()
                        
                        return self.async_create_entry(
                            title=f"ExalusHome {host}",
                            data=user_input,
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


config_entries.HANDLERS.register(ExalusHomeLocalConfigFlow)
