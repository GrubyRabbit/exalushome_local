"""WebSocket client for ExalusHome Local protocol."""

import asyncio
import json
import logging
import time
import uuid
from typing import Callable, Optional, Dict, Any

try:
    import aiohttp
except ImportError:
    aiohttp = None

try:
    import websockets
except ImportError:
    websockets = None

from .models import Device, DeviceChannel, DeviceState, ControlFeature, BlindState, TaskExecution

_LOGGER = logging.getLogger(__name__)

# WebSocket protocol constants
WEBSOCKET_RESOURCE_CONTROL = "/devices/device/control"
WEBSOCKET_RESOURCE_STATE_CHANGED = "/info/devices/device/state/changed"
WEBSOCKET_RESOURCE_LOGIN = "/users/user/login"
WEBSOCKET_RESOURCE_DEVICES_LIST = "/devices/list"
WEBSOCKET_RESOURCE_LOGOUT = "/info/users/user/loggedOut"
WEBSOCKET_RESOURCE_TASKS = "/info/devices/tasks"

# IDataFrame method enum
METHOD_GET = 0
METHOD_POST = 1
METHOD_DELETE = 2
METHOD_PUT = 3

# Status enum (from library DataFrame.Status)
STATUS_OK = 0
STATUS_UNKNOWN_ERROR = 1
STATUS_FATAL_ERROR = 2
STATUS_WRONG_DATA = 3
STATUS_RESOURCE_NOT_EXISTS = 4
STATUS_NO_PERMISSION = 5
STATUS_SESSION_ALREADY_LOGGED = 6
STATUS_OPERATION_NOT_PERMITTED = 7
STATUS_NO_PERMISSIONS_TO_RESOURCE = 8
STATUS_RESOURCE_NOT_AVAILABLE = 9
STATUS_ERROR = 10
STATUS_NO_DATA = 11
STATUS_NOT_SUPPORTED_METHOD = 12
STATUS_USER_NOT_LOGGED_IN = 13

# State data types
STATE_DATA_TYPE_BLIND_POSITION = "BlindPosition"


class ExalusLocalClient:
    """WebSocket client for ExalusHome local connection."""
    
    def __init__(self, host: str, serial: str, pin: str, email: str = None, password: str = None, port: int = 81):
        """Initialize client.
        
        Args:
            host: Controller IP address (plain host/IP, no protocol prefix)
            serial: Controller serial number
            pin: Controller PIN
            email: User email for session login (local mode)
            password: User password for session login (local mode)
            port: WebSocket port (default 81)
        """
        # Normalize host: strip protocol prefixes and trailing slashes
        self.host = self._normalize_host(host)
        self.serial = serial
        self.pin = pin
        self.email = email or "local@exalushome.local"  # Fallback to placeholder if not provided
        self.password = password or "local_pin"  # Fallback to placeholder if not provided
        self.port = port
        self.websocket = None
        self._connected = False
        self._authorized = False
        self._session_logged_in = False
        self._devices: Dict[str, Device] = {}
        self._state_callbacks = []
        self._connection_callbacks = []
        self._logout_callbacks = []
        self._task_callbacks = []
        self._receive_task = None
        self._ping_task = None
        self._last_received_packet_time: Optional[float] = None
        self._pending_responses: Dict[str, asyncio.Future] = {}  # TransactionId -> Future
        self._session_login_event: Optional[asyncio.Event] = None
    
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
        
        # Remove trailing slashes
        host = host.rstrip("/")
        
        return host
    
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
            # Step 1: HTTP authorization (local controller_info validation)
            if not await self._authorize():
                return False
            
            # Build WebSocket URL with /api endpoint
            ws_url = f"ws://{self.host}:{self.port}/api"
            _LOGGER.debug(f"Attempting WebSocket connection to: {ws_url}")
            
            if websockets is None:
                _LOGGER.error("websockets library not available")
                return False
            
            self.websocket = await websockets.connect(ws_url)
            self._connected = True
            self._last_received_packet_time = time.time()
            _LOGGER.info(f"Connected to {self.host}:{self.port}")
            
            # Start receive loop
            self._receive_task = asyncio.create_task(self._receive_loop())
            
            # Start ping keepalive loop (producer-aligned)
            self._ping_task = asyncio.create_task(self._ping_loop())
            
            # Step 2: Create session via /users/user/login
            if not await self._create_session():
                await self.disconnect()
                return False
            
            self._notify_connection_changed(True)
            return True
                
        except Exception as e:
            _LOGGER.error(f"Connection failed: {e}")
            self._connected = False
            self._notify_connection_changed(False)
            return False
    
    async def disconnect(self):
        """Disconnect from controller."""
        self._authorized = False
        self._session_logged_in = False
        self._connected = False
        
        if self._ping_task:
            self._ping_task.cancel()
            try:
                await self._ping_task
            except asyncio.CancelledError:
                pass
            self._ping_task = None
        
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
        """Authorize using HTTP controller_info endpoint (local mode auth).
        
        Returns:
            True if authorization successful
            
        Library reference: LocalNetworkExalusConnectionService.js:195-226
        - Calls HTTP GET http://{hostname}/controller_info
        - Validates response == "{SerialNumber}:{PIN}"
        """
        try:
            # Validate credentials via HTTP endpoint (local auth method)
            http_url = f"http://{self.host}/controller_info"
            _LOGGER.debug(f"Validating local controller via HTTP: {http_url}")
            
            if aiohttp is None:
                _LOGGER.error("aiohttp library not available for local auth")
                return False
            
            try:
                async with aiohttp.ClientSession() as session:
                    async with session.get(http_url, timeout=aiohttp.ClientTimeout(total=5)) as resp:
                        if resp.status != 200:
                            _LOGGER.error(f"Controller info HTTP returned {resp.status}")
                            return False
                        
                        response_text = await resp.text()
                        expected = f"{self.serial}:{self.pin}"
                        
                        if response_text.strip() == expected:
                            _LOGGER.debug(f"✓ Local controller_info validation successful: {self.serial}")
                            self._authorized = True
                            return True
                        else:
                            _LOGGER.error(f"Controller info mismatch. Expected '{expected}', got '{response_text.strip()}'")
                            return False
                            
            except asyncio.TimeoutError:
                _LOGGER.error("Local controller_info request timed out")
                return False
            except Exception as e:
                _LOGGER.error(f"Local controller_info HTTP request failed: {e}")
                return False
            
        except Exception as e:
            _LOGGER.error(f"Authorization failed: {e}")
            return False
    
    async def _create_session(self) -> bool:
        """Create session via /users/user/login WebSocket request.
        
        Returns:
            True if session creation successful
            
        Library reference: LocalNetworkExalusConnectionService.js:264
        - WaitForSessionCreationAsync prerequisite before any /devices/list request
        - SessionService handles login via /users/user/login frame
        """
        if self._session_logged_in:
            return True
        
        try:
            transaction_id = str(uuid.uuid4())
            
            # Library uses LoginUserRequest with Method.Put
            # Uses real user email and password for session login
            login_frame = {
                "TransactionId": transaction_id,
                "Resource": WEBSOCKET_RESOURCE_LOGIN,
                "Method": METHOD_PUT,
                "Data": {
                    "Email": self.email,
                    "Password": self.password
                }
            }
            
            # Create future for response
            response_future = asyncio.Future()
            self._pending_responses[transaction_id] = response_future
            
            _LOGGER.debug(f"Sending session/login request to /users/user/login (email: {self.email})")
            msg = json.dumps(login_frame)
            await self.websocket.send(msg)
            
            # Wait for login response (library timeout: 15000ms)
            try:
                response = await asyncio.wait_for(response_future, timeout=10.0)
            except asyncio.TimeoutError:
                _LOGGER.error("Session login request timed out")
                self._pending_responses.pop(transaction_id, None)
                return False
            
            # Check response status
            status = response.get("Status", STATUS_UNKNOWN_ERROR)
            if status != STATUS_OK:
                _LOGGER.error(f"Session login failed with Status {status}: {response.get('Data')}")
                return False
            
            _LOGGER.debug("✓ Session/login created successfully")
            self._session_logged_in = True
            return True
            
        except Exception as e:
            _LOGGER.error(f"Session creation failed: {e}")
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
    
    async def _ping_loop(self):
        """Keepalive ping loop (producer-aligned).
        
        Sends /system/ping every 5 seconds to keep session alive.
        Matches LocalNetworkExalusConnectionService._pingInterval = 5000ms.
        """
        ping_interval = 5.0
        
        try:
            while self._connected and self.websocket:
                await asyncio.sleep(ping_interval)
                
                if not self._connected or not self.websocket:
                    break
                
                # Check if we've received packets recently
                if self._last_received_packet_time is not None:
                    elapsed = time.time() - self._last_received_packet_time
                    if elapsed < ping_interval:
                        _LOGGER.debug(f"[PING] ping skipped because recent traffic received ({elapsed:.1f}s ago)")
                        continue
                
                # Send ping frame
                try:
                    await self._send_ping()
                except Exception as e:
                    _LOGGER.debug(f"[PING] ping failed: {e}")
                    
        except asyncio.CancelledError:
            pass
        except Exception as e:
            _LOGGER.error(f"Ping loop error: {e}")
    
    async def _send_ping(self):
        """Send /system/ping keepalive frame."""
        try:
            ping_frame = {
                "TransactionId": str(uuid.uuid4()),
                "Resource": "/system/ping",
                "Method": METHOD_GET,
            }
            
            msg = json.dumps(ping_frame)
            await self.websocket.send(msg)
            _LOGGER.debug(f"[PING] ping sent")
        except Exception as e:
            _LOGGER.error(f"[PING] failed to send ping: {e}")
            raise
    
    async def _handle_message(self, msg: str):
        """Handle received message."""
        try:
            # Track packet receive time for ping keepalive (producer-aligned)
            self._last_received_packet_time = time.time()
            
            data = json.loads(msg)
            
            # Check if this is a response to a pending request
            transaction_id = data.get("TransactionId")
            if transaction_id and transaction_id in self._pending_responses:
                future = self._pending_responses.pop(transaction_id)
                if not future.done():
                    future.set_result(data)
                return
            
            # Route by Resource field (IDataFrame protocol)
            resource = data.get("Resource")
            _LOGGER.debug(f"[STATE] Inbound frame: Resource={resource}")
            
            if resource == WEBSOCKET_RESOURCE_STATE_CHANGED:
                # Device state changed event
                message_data = data.get("Data", {})
                _LOGGER.debug(f"[STATE] State changed event Data: {message_data}")
                
                # Check if this is a BlindPosition update
                data_type = message_data.get("DataType")
                _LOGGER.debug(f"[STATE] DataType: {data_type}")
                if data_type == STATE_DATA_TYPE_BLIND_POSITION:
                    _LOGGER.debug(f"[STATE-RAW] BlindPosition frame detected")
                    _LOGGER.debug(f"[STATE-RAW] FULL RAW FRAME: {json.dumps(data, indent=2)}")
                    
                    device_guid = message_data.get("DeviceGuid")
                    state_obj = message_data.get("state", {})
                    channel = state_obj.get("Channel")
                    position = state_obj.get("Position")
                    raw_position = state_obj.get("RawPosition")
                    
                    _LOGGER.debug(f"[STATE-RAW] PARSED: DeviceGuid={device_guid}")
                    _LOGGER.debug(f"[STATE-RAW] PARSED: DataType={data_type}")
                    _LOGGER.debug(f"[STATE-RAW] PARSED: state.Channel={channel}")
                    _LOGGER.debug(f"[STATE-RAW] PARSED: state.Position={position}")
                    _LOGGER.debug(f"[STATE-RAW] PARSED: state.RawPosition={raw_position}")
                    
                    await self._on_blind_position_changed(message_data)
                else:
                    _LOGGER.debug(f"[STATE] Ignoring non-BlindPosition DataType: {data_type}")
            elif resource == WEBSOCKET_RESOURCE_LOGOUT:
                # Session logged out event
                _LOGGER.debug(f"[SESSION] loggedOut received")
                self._session_logged_in = False
                self._notify_logout()
            elif resource == WEBSOCKET_RESOURCE_TASKS:
                # Device tasks execution event — source of truth for movement state
                # Data is an array of "DeviceGuid;Channel" strings for currently running tasks
                # Empty array means all tasks stopped
                tasks_data = data.get("Data", [])
                _LOGGER.debug(f"[LIVE] task event received: {tasks_data}")
                self._notify_task_changed(tasks_data)
            else:
                _LOGGER.debug(f"[STATE] Ignoring message with resource: {resource}")
                
        except json.JSONDecodeError:
            _LOGGER.debug(f"Failed to parse message: {msg}")
        except Exception as e:
            _LOGGER.error(f"Error handling message: {e}")
    
    async def _on_blind_position_changed(self, state_data: Dict[str, Any]):
        """Handle blind position changed event.
        
        Args:
            state_data: Data from /info/devices/device/state/changed with DataType=BlindPosition
                - DeviceGuid: device GUID
                - Channel: channel number
                - state.Position: position value (Exalus scale: 0=open, 100=closed)
                - state.TaskExecution: 0=idle, 1=executing/moving
                - Other state information
        """
        device_guid = state_data.get("DeviceGuid", "?")
        channel = state_data.get("Channel", "?")
        state_info = state_data.get("state", {})
        position_exalus = state_info.get("Position", "?")
        task_execution = state_info.get("TaskExecution", "?")
        
        _LOGGER.debug(
            f"Blind position changed: device={device_guid}, channel={channel}, "
            f"Exalus_Position={position_exalus}, TaskExecution={task_execution}"
        )
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
    
    def on_logout(self, callback: Callable):
        """Register logout callback.
        
        Args:
            callback: Async function() called when session is logged out
        """
        self._logout_callbacks.append(callback)
    
    def on_task_changed(self, callback: Callable):
        """Register device tasks changed callback.
        
        Args:
            callback: Async function(tasks: list) called when /info/devices/tasks fires.
                      tasks is a list of "DeviceGuid;Channel" strings for currently running tasks.
                      Empty list means all tasks have stopped.
        """
        self._task_callbacks.append(callback)
    
    def _notify_state_changed(self, state_data: Dict[str, Any]):
        """Notify all state change listeners."""
        _LOGGER.debug(f"[STATE] Notifying {len(self._state_callbacks)} callback(s) with state_data")
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
    
    def _notify_logout(self):
        """Notify all logout listeners."""
        for callback in self._logout_callbacks:
            try:
                asyncio.create_task(callback())
            except Exception as e:
                _LOGGER.error(f"Logout callback error: {e}")
    
    def _notify_task_changed(self, tasks_data: list):
        """Notify all device task change listeners.
        
        Args:
            tasks_data: List of "DeviceGuid;Channel" strings for currently running tasks.
                        Empty list means all tasks stopped.
        """
        for callback in self._task_callbacks:
            try:
                asyncio.create_task(callback(tasks_data))
            except Exception as e:
                _LOGGER.error(f"Task callback error: {e}")
    
    async def fetch_devices(self) -> Dict[str, Device]:
        """Fetch device list from controller.
        
        Returns:
            Dictionary of devices indexed by GUID
        
        EXACT EVIDENCE:
        Source: /tmp/exalushome_packages/lavva_exalushome/package/build/js/Services/Devices/DevicesService.js
        
        DevicesService.GetPairedDevicesAsync() calls:
            this._connection.SendAndWaitForResponseAsync(new GetDevicesListRequest(), 15000, true)
        
        GetDevicesListRequest class definition:
            class GetDevicesListRequest extends DataFrame {
                constructor() {
                    super();
                    this.Resource = "/devices/list";
                    this.Method = Method.Get;
                }
            }
        
        Response handling:
            if (result.Status == Status.OK && result.Data != null) {
                this._devices = this.MapApiDevices(result.Data);
                return this._devices;
            }
        """
        if not self.is_connected:
            _LOGGER.error("Not connected to controller")
            return {}
        
        if not self._session_logged_in:
            _LOGGER.warning("Session not established, waiting for login...")
            if not await self._create_session():
                _LOGGER.error("Cannot create session, aborting device fetch")
                return {}
        
        try:
            transaction_id = str(uuid.uuid4())
            
            # Send GetDevicesListRequest (exact endpoint confirmed from npm library)
            request_frame = {
                "TransactionId": transaction_id,
                "Resource": WEBSOCKET_RESOURCE_DEVICES_LIST,
                "Method": METHOD_GET,
            }
            
            # Create future for response
            response_future = asyncio.Future()
            self._pending_responses[transaction_id] = response_future
            
            msg = json.dumps(request_frame)
            await self.websocket.send(msg)
            _LOGGER.debug(f"Device list request sent (TransactionId: {transaction_id})")
            
            # Wait for response with timeout (npm uses 15000ms)
            try:
                response = await asyncio.wait_for(response_future, timeout=10.0)
            except asyncio.TimeoutError:
                _LOGGER.error("Device list request timed out")
                self._pending_responses.pop(transaction_id, None)
                return {}
            
            # Check response status BEFORE accessing Data (library: DevicesService.js:777)
            status = response.get("Status", STATUS_UNKNOWN_ERROR)
            if status != STATUS_OK:
                _LOGGER.error(
                    f"Device list request failed: Status={status} "
                    f"(USER_NOT_LOGGED_IN=13), Data={response.get('Data')}"
                )
                return {}
            
            # Parse response and convert to Device objects
            devices = self._parse_device_list_response(response)
            _LOGGER.info(f"Fetched {len(devices)} device(s)")
            return devices
            
        except Exception as e:
            _LOGGER.error(f"Device fetch failed: {e}")
            return {}
    
    def _parse_device_list_response(self, response: Dict[str, Any]) -> Dict[str, Device]:
        """Parse device list response and convert to Device objects.
        
        Args:
            response: IDataFrame response containing device data
            
        Returns:
            Dictionary of Device objects indexed by GUID
        
        EXACT EVIDENCE:
        Source: /tmp/exalushome_packages/lavva_exalushome/package/build/js/Services/Devices/DevicesService.js
        
        MapApiDevices implementation shows response.Data is array of objects with:
            Guid, DeviceName, ChannelsNumber, DeviceType, CommunicationWay, DeviceState,
            IsEnabled, IsVirtual, DeviceSerialNumber, ManufacturerGuid, DeviceModelGuid,
            DeviceModel, IconType, AvailableTasks[], AvailableResponses[], Channels[]
        
        Channel identification: "IBlindPosition" in AvailableTasks indicates blind/shutter
        """
        devices = {}
        
        try:
            # Verify Status before accessing Data (library: DevicesService.js:777)
            status = response.get("Status", STATUS_UNKNOWN_ERROR)
            if status != STATUS_OK:
                _LOGGER.error(
                    f"Cannot parse device response: Status={status}, "
                    f"expected Status.OK (0)"
                )
                return {}
            
            response_data = response.get("Data")
            
            # If Data is null/None, log clearly
            if response_data is None:
                _LOGGER.error("Device list response contains no data (Data=null)")
                return {}
            
            # Handle both array and dict responses
            if isinstance(response_data, dict):
                response_data = [response_data]
            
            if not isinstance(response_data, list):
                _LOGGER.error(f"Unexpected response Data format: {type(response_data)}")
                return {}
            
            _LOGGER.debug(f"Parsing {len(response_data)} device(s) from response")
            
            for device_obj in response_data:
                try:
                    device_guid = device_obj.get("Guid")
                    if not device_guid:
                        _LOGGER.debug("Skipping device without GUID")
                        continue
                    
                    # Parse channels - field name from npm: ChannelsConfiguration array
                    channels_count = device_obj.get("ChannelsNumber", 0)
                    channels_config = device_obj.get("ChannelsConfiguration", [])
                    
                    # If ChannelsConfiguration is present, use it (library evidence: DevicesService.js line 710)
                    # If not, infer from ChannelsNumber as fallback
                    if not channels_config and channels_count > 0:
                        channels_config = [
                            {
                                "Channel": i,
                                "ChannelName": f"Channel {i}",
                            }
                            for i in range(channels_count)
                        ]
                    
                    # Parse channels into DeviceChannel objects
                    channel_list = []
                    available_tasks = device_obj.get("AvailableTasks", [])
                    
                    for ch_obj in channels_config:
                        try:
                            _LOGGER.debug(f"[ENUM] Parsing channel config: {ch_obj}")
                            
                            # Use official API response fields from ChannelsConfiguration (library DevicesService.js line 714, 717)
                            ch_number = ch_obj.get("Channel", 0)
                            ch_name = ch_obj.get("ChannelName", f"Channel {ch_number}")
                            
                            # Check if device has blind control capability
                            # Evidence: AvailableTasks contains "IBlindPosition" or "IBlindPositionSimple" for blind channels
                            is_blind = "IBlindPosition" in available_tasks or "IBlindPositionSimple" in available_tasks
                            
                            control_feature = ControlFeature.Blind if is_blind else ControlFeature.Unknown
                            
                            channel = DeviceChannel(
                                guid=f"{device_guid}_ch{ch_number}",
                                number=ch_number,
                                name=ch_name,
                                control_feature=control_feature,
                                available=True,
                            )
                            channel_list.append(channel)
                        except Exception as e:
                            _LOGGER.debug(f"Failed to parse channel: {e}")
                    
                    # Create Device object - field names from npm MapApiDevices
                    device_state_val = device_obj.get("DeviceState", DeviceState.NotResponding)
                    device = Device(
                        guid=device_guid,
                        name=device_obj.get("DeviceName", f"Device {device_guid}"),
                        state=DeviceState(device_state_val),
                        serial_number=device_obj.get("DeviceSerialNumber"),
                        software_version=None,  # Not in response
                        model=device_obj.get("DeviceModel"),
                        channels=channel_list,
                    )
                    devices[device_guid] = device
                    _LOGGER.debug(f"Added device: {device.name} ({device_guid}) with {len(channel_list)} channel(s)")
                    
                except Exception as e:
                    _LOGGER.error(f"Failed to parse device object: {e}")
                    
        except Exception as e:
            _LOGGER.error(f"Failed to parse device list response: {e}")
        
        return devices
