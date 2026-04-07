"""WebSocket client for ExalusHome Local protocol."""

import asyncio
import json
import logging
import uuid
from typing import Callable, Optional, Dict, Any

try:
    import websockets
except ImportError:
    websockets = None

from .models import Device, DeviceChannel, DeviceState, ControlFeature, BlindState, TaskExecution

_LOGGER = logging.getLogger(__name__)

# WebSocket protocol constants
WEBSOCKET_RESOURCE_CONTROL = "/devices/device/control"
WEBSOCKET_RESOURCE_STATE_CHANGED = "/info/devices/device/state/changed"

# IDataFrame method enum
METHOD_GET = 0
METHOD_POST = 1
METHOD_DELETE = 2
METHOD_PUT = 3

# State data types
STATE_DATA_TYPE_BLIND_POSITION = "BlindPosition"


class ExalusLocalClient:
    """WebSocket client for ExalusHome local connection."""
    
    def __init__(self, host: str, serial: str, pin: str, port: int = 81):
        """Initialize client.
        
        Args:
            host: Controller IP address
            serial: Controller serial number
            pin: Controller PIN
            port: WebSocket port (default 81)
        """
        self.host = host
        self.serial = serial
        self.pin = pin
        self.port = port
        self.websocket = None
        self._connected = False
        self._authorized = False
        self._devices: Dict[str, Device] = {}
        self._state_callbacks = []
        self._connection_callbacks = []
        self._receive_task = None
        
    @property
    def is_connected(self) -> bool:
        """Check if connected."""
        return self._connected
    
    @property
    def is_authorized(self) -> bool:
        """Check if authorized."""
        return self._authorized
    
    async def connect(self) -> bool:
        """Connect to local controller.
        
        Returns:
            True if connection successful and authorized
        """
        try:
            ws_url = f"ws://{self.host}:{self.port}/"
            _LOGGER.debug(f"Connecting to {ws_url}")
            
            if websockets is None:
                _LOGGER.error("websockets library not available")
                return False
            
            self.websocket = await websockets.connect(ws_url)
            self._connected = True
            _LOGGER.info(f"Connected to {self.host}:{self.port}")
            
            # Start receive loop
            self._receive_task = asyncio.create_task(self._receive_loop())
            
            # Authorize
            if await self._authorize():
                self._authorized = True
                self._notify_connection_changed(True)
                return True
            else:
                await self.disconnect()
                return False
                
        except Exception as e:
            _LOGGER.error(f"Connection failed: {e}")
            self._connected = False
            self._notify_connection_changed(False)
            return False
    
    async def disconnect(self):
        """Disconnect from controller."""
        self._authorized = False
        self._connected = False
        
        if self._receive_task:
            self._receive_task.cancel()
            try:
                await self._receive_task
            except asyncio.CancelledError:
                pass
            self._receive_task = None
        
        if self.websocket:
            try:
                await self.websocket.close()
            except Exception as e:
                _LOGGER.debug(f"Error closing websocket: {e}")
            self.websocket = None
        
        self._notify_connection_changed(False)
        _LOGGER.info("Disconnected")
    
    async def _authorize(self) -> bool:
        """Send authorization frame.
        
        Returns:
            True if authorization successful
        """
        try:
            auth_frame = {
                "TransactionId": str(uuid.uuid4()),
                "Resource": "/system/authorize",
                "Method": METHOD_POST,
                "Data": {
                    "SerialNumber": self.serial,
                    "PIN": self.pin,
                }
            }
            
            msg = json.dumps(auth_frame)
            await self.websocket.send(msg)
            _LOGGER.debug("Authorization frame sent")
            return True
            
        except Exception as e:
            _LOGGER.error(f"Authorization failed: {e}")
            return False
    
    async def _receive_loop(self):
        """Receive loop for WebSocket messages."""
        try:
            while self._connected and self.websocket:
                msg = await self.websocket.recv()
                await self._handle_message(msg)
        except asyncio.CancelledError:
            pass
        except Exception as e:
            _LOGGER.error(f"Receive loop error: {e}")
            await self.disconnect()
    
    async def _handle_message(self, msg: str):
        """Handle received message."""
        try:
            data = json.loads(msg)
            
            # Route by Resource field (IDataFrame protocol)
            resource = data.get("Resource")
            
            if resource == WEBSOCKET_RESOURCE_STATE_CHANGED:
                # Device state changed event
                message_data = data.get("Data", {})
                
                # Check if this is a BlindPosition update
                data_type = message_data.get("DataType")
                if data_type == STATE_DATA_TYPE_BLIND_POSITION:
                    await self._on_blind_position_changed(message_data)
            else:
                _LOGGER.debug(f"Ignoring message with resource: {resource}")
                
        except json.JSONDecodeError:
            _LOGGER.debug(f"Failed to parse message: {msg}")
        except Exception as e:
            _LOGGER.error(f"Error handling message: {e}")
    
    async def _on_blind_position_changed(self, state_data: Dict[str, Any]):
        """Handle blind position changed event.
        
        Args:
            state_data: Data from the state change event containing:
                - DeviceGuid: device GUID
                - Channel: channel number
                - state.Position: position value (Exalus scale: 0=open, 100=closed)
                - Other state information
        """
        _LOGGER.debug(f"Blind position changed: {state_data}")
        self._notify_state_changed(state_data)
    
    async def send_command(
        self,
        device_guid: str,
        channel_number: int,
        command: int,
    ) -> bool:
        """Send command to device.
        
        Args:
            device_guid: Device GUID
            channel_number: Channel number
            command: Command code (101=open, 102=close, 103=stop, or position 0-100)
        
        Returns:
            True if command sent successfully
        """
        if not self._authorized:
            _LOGGER.error("Not authorized")
            return False
        
        try:
            # Build IDataFrame with exact protocol format
            frame = {
                "TransactionId": str(uuid.uuid4()),
                "Resource": WEBSOCKET_RESOURCE_CONTROL,
                "Method": METHOD_POST,
                "Data": {
                    "DeviceGuid": device_guid,
                    "Channel": channel_number,
                    "ControlFeature": 3,  # Blind control
                    "SequnceExecutionOrder": 0,
                    "Data": command  # 101=open, 102=close, 103=stop, or 0-100=position
                }
            }
            
            msg = json.dumps(frame)
            await self.websocket.send(msg)
            _LOGGER.debug(
                f"Command sent: device={device_guid}, channel={channel_number}, "
                f"command={command}"
            )
            return True
            
        except Exception as e:
            _LOGGER.error(f"Send command failed: {e}")
            return False
    
    def on_state_changed(self, callback: Callable):
        """Register state change callback.
        
        Args:
            callback: Async function(state_data: Dict) called on state changes
        """
        self._state_callbacks.append(callback)
    
    def on_connection_changed(self, callback: Callable):
        """Register connection state callback.
        
        Args:
            callback: Async function(connected: bool) called on connection changes
        """
        self._connection_callbacks.append(callback)
    
    def _notify_state_changed(self, state_data: Dict[str, Any]):
        """Notify all state change listeners."""
        for callback in self._state_callbacks:
            try:
                asyncio.create_task(callback(state_data))
            except Exception as e:
                _LOGGER.error(f"Callback error: {e}")
    
    def _notify_connection_changed(self, connected: bool):
        """Notify all connection change listeners."""
        for callback in self._connection_callbacks:
            try:
                asyncio.create_task(callback(connected))
            except Exception as e:
                _LOGGER.error(f"Callback error: {e}")
    
    async def fetch_devices(self) -> Dict[str, Device]:
        """Fetch device list from controller.
        
        Returns:
            Dictionary of devices indexed by GUID
        """
        # TODO: Implement device fetch via local API
        # This would typically be a GET request to an HTTP endpoint
        # or a specific WebSocket message requesting device list
        _LOGGER.warning("Device fetch not yet implemented")
        return {}
