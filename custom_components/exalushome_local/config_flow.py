"""Config flow for ExalusHome Local."""

from typing import Any, Dict, Optional
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResult

from .const import DOMAIN, CONF_HOST, CONF_SERIAL, CONF_PIN, CONF_EMAIL, CONF_PASSWORD
from .api.client import ExalusLocalClient

import logging
_LOGGER = logging.getLogger(__name__)


class ExalusHomeLocalConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Config flow for ExalusHome Local."""
    
    VERSION = 1
    
    async def async_step_user(
        self, user_input: Optional[Dict[str, Any]] = None
    ) -> FlowResult:
        """Handle step 1: Controller connection info."""
        errors = {}
        
        if user_input is not None:
            try:
                host = user_input.get(CONF_HOST, "").strip()
                host = self._normalize_host(host)
                
                serial = user_input.get(CONF_SERIAL, "").strip()
                pin = user_input.get(CONF_PIN, "").strip()
                
                if not host or not serial or not pin:
                    errors["base"] = "invalid_input"
                elif "/" in host or "://" in host:
                    errors[CONF_HOST] = "invalid_host"
                else:
                    # Store step 1 data in context for step 2
                    self.context["step1_data"] = {
                        CONF_HOST: host,
                        CONF_SERIAL: serial,
                        CONF_PIN: pin,
                    }
                    
                    # Proceed to step 2 for user credentials
                    return await self.async_step_user_credentials()
                    
            except Exception as e:
                _LOGGER.error(f"Config flow error: {e}")
                errors["base"] = "unknown_error"
        
        # Show step 1 form
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
    
    async def async_step_user_credentials(
        self, user_input: Optional[Dict[str, Any]] = None
    ) -> FlowResult:
        """Handle step 2: User credentials for session login."""
        errors = {}
        
        if user_input is not None:
            try:
                email = user_input.get(CONF_EMAIL, "").strip()
                password = user_input.get(CONF_PASSWORD, "").strip()
                
                if not email or not password:
                    errors["base"] = "invalid_input"
                else:
                    # Get step 1 data from context
                    step1_data = self.context.get("step1_data", {})
                    host = step1_data.get(CONF_HOST)
                    serial = step1_data.get(CONF_SERIAL)
                    pin = step1_data.get(CONF_PIN)
                    
                    # Test connection with all credentials
                    client = ExalusLocalClient(host, serial, pin, email, password)
                    if await client.connect():
                        await client.disconnect()
                        
                        # Check for duplicate entries
                        await self.async_set_unique_id(serial)
                        self._abort_if_unique_id_configured()
                        
                        # Combine both steps data
                        config_data = {
                            CONF_HOST: host,
                            CONF_SERIAL: serial,
                            CONF_PIN: pin,
                            CONF_EMAIL: email,
                            CONF_PASSWORD: password,
                        }
                        
                        return self.async_create_entry(
                            title=f"ExalusHome {host}",
                            data=config_data,
                        )
                    else:
                        errors["base"] = "cannot_connect"
            except Exception as e:
                _LOGGER.error(f"Config flow error: {e}")
                errors["base"] = "unknown_error"
        
        # Show step 2 form
        return self.async_show_form(
            step_id="user_credentials",
            data_schema=vol.Schema({
                vol.Required(CONF_EMAIL): str,
                vol.Required(CONF_PASSWORD): str,
            }),
            errors=errors,
            description_placeholders={},
        )
    
    @staticmethod
    def _normalize_host(host: str) -> str:
        """Normalize host by removing protocol prefixes and trailing slashes."""
        host = host.strip()
        
        # Remove protocol prefixes
        for prefix in ("wss://", "ws://", "https://", "http://"):
            if host.lower().startswith(prefix):
                host = host[len(prefix):]
        
        # Remove trailing slashes and paths
        host = host.rstrip("/").split("/")[0]
        
        return host


config_entries.HANDLERS.register(ExalusHomeLocalConfigFlow)
