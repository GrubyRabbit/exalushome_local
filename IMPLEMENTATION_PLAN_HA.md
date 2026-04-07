# Implementation Plan: ExalusHome HA Shutter Integration

## 1. Confirmed Remote Auth Flow

**Source:** `lavva.exalushome` v2.1.4 - `ExalusConnectionService`

```python
# Step 1: Create credentials
auth_info = AuthorizationInfo(
    serial_number="ABC123DEF456",  # Controller serial
    pin="0000"                      # Controller PIN
)

# Step 2: Connect and authorize
connection_service = ExalusConnectionService()
result = await connection_service.ConnectAndAuthorizeAsync(auth_info)

# Step 3: Check result
if result == ConnectionResult.Connected:  # value = 3
    # Ready to send commands
else:
    # Handle errors:
    # FailedToConnect = 0
    # AuthorizationFailed = 1
    # FailedToConnectToServer = 2
    # ControllerIsNotConnected = 4
```

**Protocol Details:**
- Transport: Microsoft SignalR over WebSocket
- Broker: `exalushome.tr7.pl` (inferred from source)
- Backup brokers: `exalushome-backup.tr7.pl`, `exalushome-fallback.tr7.pl`
- Keep-alive: `PingControllerAsync()` method available
- Connection state event: `OnConnectionStateChangedEvent()` subscription

**Frame Protocol (HTTP-like):**
```python
request = IDataFrame(
    Resource="/devices/{device_guid}/executeTask",
    TransactionId="req_001",
    Method=1,  # Post
    Data={
        "taskType": "IBlindPosition",
        "position": 50
    }
)

response = await connection_service.SendAndWaitForResponseAsync(
    request,
    timeout=5000,
    useCache=False
)

# Response
{
    "Status": 0,  # OK
    "Data": {...}
}
```

---

## 2. Confirmed Local Auth Flow

**Source:** `lavva.exalushome` v2.1.4 - `LocalNetworkExalusConnectionService`

```python
# Step 1: Create credentials (same as remote)
auth_info = AuthorizationInfo(
    serial_number="ABC123DEF456",
    pin="0000"
)

# Step 2: Connect to local controller
local_service = LocalNetworkExalusConnectionService()
result = await local_service.ConnectAndAuthorizeAsync(auth_info)

# Step 3: Connection details
# WebSocket URL: ws://controller_ip:81/
# Port: 81 (hardcoded, not configurable)
# Protocol: Custom binary over WebSocket
# TLS/SSL: None (plain WebSocket)
```

**Key Differences from Remote:**
- Port: 81 (hardcoded)
- No broker failover (single endpoint)
- Streams NOT supported: `SendAndHandleStreamAsync()` returns error
- Ping endpoint: `/system/ping` (HTTP GET)
- Validation endpoint: `http://controller_ip/controller_info` returns `SERIAL:PIN` format
- Ping interval: 5000ms (hardcoded)
- Supports caching: `useCache=True` parameter

**Frame Protocol:** Identical to remote (`IDataFrame<T>`)

---

## 3. Confirmed Shutter Entity Schema

**Device Structure:**
```python
class ShutterDevice:
    guid: str                           # From IDevice.Guid
    name: str                           # From IDevice.Name
    available: bool                     # From IDevice.DeviceState
                                        # Working=1 → True
                                        # NotResponding=0 → False
                                        # Broken=2 → False
                                        # FirmwareUpgradeMode=3 → False
    
    # Per-channel state
    channels: List[ShutterChannel]      # IDevice.Channels[]
```

**Channel Filtering (Shutter Only):**
```python
SHUTTER_ROLES = {11, 12, 21, 23}       # From Roles enum
                # Blind, Roller, BlindsWithPrecisePosition, BlindsRemote

for channel in device.channels:
    if any(role in SHUTTER_ROLES for role in channel.roles):
        # Include this channel as CoverEntity
```

**State Fields Available:**
```python
class ShutterState:
    position: int | None                # From IDeviceState.Data
                                        # Type="IBlindPosition"
                                        # SCALE UNKNOWN - SEE UNKNOWNS
    is_moving: bool                     # From TaskExecution enum
                                        # ExecutingTasks=1 → True
                                        # NoTasksExecuting=0 → False
    supports_exact_position: bool       # From AvailableTaskTypes
                                        # SetBlindPosition in list
    error_state: int | None             # From IDeviceState.Data
                                        # Type="IBlindError"
    open_close_time: int | None         # From IDeviceState.Data
                                        # Type="IBlindOpenCloseTime"
```

**Entity ID Mapping:**
```python
unique_id = f"exalushome_{device.guid}_{channel.guid}"
```

---

## 4. Confirmed Command Schema

**All Commands Use Same Task Execution Model:**

```python
class ShutterCommand:
    device_guid: str
    channel_guid: str
    task_type: str                      # From DeviceTaskType enum
    data: dict                          # Payload varies by task_type
```

### Open Command
```python
command = ShutterCommand(
    task_type="SetBlindPosition",       # From DeviceTaskType enum
    data={"position": ???}              # UNKNOWN: 0 or 100?
)
await channel.ExecuteTaskAsync(command)
```

### Close Command
```python
command = ShutterCommand(
    task_type="SetBlindPosition",
    data={"position": ???}              # UNKNOWN: 100 or 0?
)
await channel.ExecuteTaskAsync(command)
```

### Set Exact Position
```python
command = ShutterCommand(
    task_type="SetBlindPosition",
    data={"position": 50}               # ASSUMING 0-100 scale
)
await channel.ExecuteTaskAsync(command)
```

### Stop Command
```python
# OPTION 1: SetBlindPositionSimple (likely)
command = ShutterCommand(
    task_type="SetBlindPositionSimple",
    data={???}                          # UNKNOWN: Payload structure
)

# OPTION 2: Unknown mechanism
# REQUIRES VALIDATION
```

**Capability Detection (Before Exposing Command):**
```python
for task_type in channel.available_task_types:
    if task_type == "SetBlindPosition":
        supports_set_position = True
    if task_type == "SetBlindPositionSimple":
        supports_stop = True
```

---

## 5. Exact Unknowns Requiring Validation

### BLOCKING UNKNOWNS (Must Validate Before Implementation)

**1. Position Scale** 🔴 CRITICAL
- Question: What values are valid for `SetBlindPosition.data.position`?
- Options: 0-100% | 0-255 (8-bit) | 0-180° (degrees) | Other
- Current assumption: 0-100%
- Validation method: Move blind in web app to 0%, 50%, 100% positions, capture `/devices/{id}/state` responses
- Impact: Determines open/close direction mapping in HA
- Location of answer: Response `Data` field in position state, likely integer field

**2. Stop Command Payload** 🔴 CRITICAL
- Question: How to stop blind mid-movement?
- Options:
  - `SetBlindPositionSimple` with special value
  - Dedicated task type
  - Send current position
- Current assumption: SetBlindPositionSimple exists but structure unknown
- Validation method: Click Stop in web app while blind moving, capture API call in DevTools
- Impact: Affects CoverEntity.STOP feature availability
- Location of answer: `/devices/{id}/executeTask` POST payload when Stop clicked

**3. Open vs Close Direction** 🟡 IMPORTANT
- Question: Which direction is 0, which is 100?
- Current assumption: 100=closed (standard HA convention)
- Validation method: Move blind fully open, check state. Move fully closed, check state. Compare position values.
- Impact: Determines `is_open`, `is_closed`, `async_open_cover()` logic
- Location of answer: `/devices/{id}/state` position field when blind fully open vs fully closed

### NICE-TO-HAVE (Can implement with sensible defaults if validation unavailable)

**4. Movement Direction Detection**
- Question: Can we distinguish `is_opening` vs `is_closing`?
- Current: `TaskExecution` flag shows "moving" but not direction
- Would need: Additional state field or bi-directional tracking
- Impact: Affects `is_opening`/`is_closing` properties
- Fallback: Set both to match `is_moving`

**5. State Update Frequency**
- Question: Push updates vs polling interval?
- Current: Can use polling with reasonable interval
- Impact: Coordinator update frequency
- Fallback: 30-second polling interval

---

## 6. Minimal Python API Client Design

### Layer 1: Data Models

```python
# File: exalushome_api/models.py

from dataclasses import dataclass
from enum import Enum
from typing import Optional

class ConnectionMode(Enum):
    REMOTE = "remote"
    LOCAL = "local"

class DeviceState(Enum):
    WORKING = 1
    NOT_RESPONDING = 0
    BROKEN = 2
    FIRMWARE_UPDATE = 3

@dataclass
class AuthInfo:
    serial_number: str
    pin: str

@dataclass
class ShutterDevice:
    guid: str
    name: str
    available: bool
    position: Optional[int]  # SCALE UNKNOWN
    is_moving: bool
    supports_exact_position: bool
    error_state: Optional[int] = None

@dataclass
class ShutterCommand:
    device_guid: str
    channel_guid: str
    action: str  # "open", "close", "stop", "set_position"
    position: Optional[int] = None  # For set_position

class TaskExecutionResult(Enum):
    SUCCESS = 0
    IN_PROGRESS = 1
    FAILED = 2
    NOT_SUPPORTED = 3
```

### Layer 2: Abstract Transport Interface

```python
# File: exalushome_api/transport.py

from abc import ABC, abstractmethod
from typing import Any, Dict, Optional

class IDataFrame:
    def __init__(
        self,
        resource: Optional[str] = None,
        transaction_id: Optional[str] = None,
        method: int = 0,
        data: Optional[Dict[str, Any]] = None,
        status: Optional[int] = None
    ):
        self.Resource = resource
        self.TransactionId = transaction_id
        self.Method = method
        self.Data = data
        self.Status = status

class Transport(ABC):
    """Abstract transport for both SignalR (remote) and WebSocket (local)."""
    
    @abstractmethod
    async def connect(self, auth: AuthInfo) -> bool:
        """Connect and authorize."""
        pass
    
    @abstractmethod
    async def disconnect(self) -> None:
        """Disconnect."""
        pass
    
    @abstractmethod
    async def send_and_wait(
        self,
        frame: IDataFrame,
        timeout_ms: int = 5000
    ) -> IDataFrame:
        """Send frame and wait for response."""
        pass
    
    @abstractmethod
    def on_connection_state_changed(self, callback):
        """Register callback for connection state changes."""
        pass
    
    @abstractmethod
    def on_data_received(self, callback):
        """Register callback for unsolicited updates."""
        pass
```

### Layer 3: Concrete Transports

```python
# File: exalushome_api/remote.py

class RemoteTransport(Transport):
    """SignalR-based transport to cloud broker."""
    
    def __init__(self):
        self._service = None  # ExalusConnectionService()
        self._auth = None
    
    async def connect(self, auth: AuthInfo) -> bool:
        self._auth = auth
        # TODO: Initialize ExalusConnectionService
        # TODO: Call ConnectAndAuthorizeAsync(auth)
        # TODO: Handle ConnectionResult enum
        return True
    
    async def disconnect(self) -> None:
        # TODO: Call DisconnectAsync()
        pass
    
    async def send_and_wait(self, frame: IDataFrame, timeout_ms: int = 5000) -> IDataFrame:
        # TODO: Call SendAndWaitForResponseAsync()
        # TODO: Map IDataFrame to/from JS transport format
        return frame
    
    def on_connection_state_changed(self, callback):
        # TODO: Subscribe to OnConnectionStateChangedEvent()
        pass
    
    def on_data_received(self, callback):
        # TODO: Subscribe to OnDataReceivedEvent()
        pass
```

```python
# File: exalushome_api/local.py

class LocalTransport(Transport):
    """WebSocket-based transport to local controller on port 81."""
    
    def __init__(self, host: str, port: int = 81):
        self._host = host
        self._port = port
        self._auth = None
        self._ws = None
    
    async def connect(self, auth: AuthInfo) -> bool:
        self._auth = auth
        # TODO: WebSocket connect to ws://host:port/
        # TODO: Call ConnectAndAuthorizeAsync(auth)
        # TODO: Set up ping interval (5000ms)
        return True
    
    async def disconnect(self) -> None:
        # TODO: Close WebSocket
        pass
    
    async def send_and_wait(self, frame: IDataFrame, timeout_ms: int = 5000) -> IDataFrame:
        # TODO: Serialize IDataFrame to binary
        # TODO: Send over WebSocket
        # TODO: Wait for response with timeout
        # TODO: Deserialize response
        return frame
    
    def on_connection_state_changed(self, callback):
        # TODO: Hook WebSocket state changes
        pass
    
    def on_data_received(self, callback):
        # TODO: Hook incoming WebSocket messages
        pass
```

### Layer 4: High-Level API

```python
# File: exalushome_api/api.py

from abc import ABC, abstractmethod
from typing import List

class ExalusShutterAPI(ABC):
    """Abstract API hiding both transport modes."""
    
    @abstractmethod
    async def connect(self) -> bool:
        pass
    
    @abstractmethod
    async def disconnect(self) -> None:
        pass
    
    @abstractmethod
    async def get_shutters(self) -> List[ShutterDevice]:
        """Get all shutters across all devices."""
        pass
    
    @abstractmethod
    async def get_shutter(self, device_guid: str, channel_guid: str) -> ShutterDevice:
        """Get specific shutter state."""
        pass
    
    @abstractmethod
    async def execute_command(self, cmd: ShutterCommand) -> bool:
        """Execute command (open/close/stop/set_position)."""
        pass

class RemoteShutterAPI(ExalusShutterAPI):
    """Cloud-based API using SignalR."""
    
    def __init__(self, username: str, password: str, serial: str, pin: str):
        self.transport = RemoteTransport()
        self.auth = AuthInfo(serial, pin)
        self.username = username
        self.password = password
    
    async def connect(self) -> bool:
        # TODO: Authenticate with ExalusHome cloud first
        # TODO: Then call transport.connect(auth)
        return await self.transport.connect(self.auth)
    
    async def get_shutters(self) -> List[ShutterDevice]:
        # TODO: Call /devices endpoint
        # TODO: Filter by SHUTTER_ROLES
        # TODO: Return list of ShutterDevice
        pass

class LocalShutterAPI(ExalusShutterAPI):
    """Local network API using WebSocket on port 81."""
    
    def __init__(self, host: str, port: int, serial: str, pin: str):
        self.transport = LocalTransport(host, port)
        self.auth = AuthInfo(serial, pin)
    
    async def connect(self) -> bool:
        # TODO: Validate controller_info endpoint first
        # TODO: Then call transport.connect(auth)
        return await self.transport.connect(self.auth)
    
    async def get_shutters(self) -> List[ShutterDevice]:
        # TODO: Same as remote
        pass
```

---

## 7. Transport Abstraction for Remote/Local

**Both modes use identical interface:**

```
Client Code (HA integration)
        ↓
ExalusShutterAPI (abstract)
        ↓
    [Factory decides]
        ↓
    ┌───┴────┐
    ↓        ↓
Remote   Local
API      API
    ↓        ↓
Transport  Transport
(SignalR)  (WebSocket:81)
    ↓        ↓
Network  Network
```

**Single interface, two implementations:**
- Both use `IDataFrame` protocol
- Both use `AuthInfo(serial, pin)` auth
- Both have `SendAndWaitForResponseAsync(frame, timeout)`
- Differences hidden: connection mechanism, keep-alive, error recovery

---

## 8. Home Assistant File Layout

```
custom_components/exalushome/
├── __init__.py                    # Setup flow, config entry handler
├── manifest.json                  # Integration metadata
├── strings.json                   # Translations
├── const.py                       # Constants (domain, versions, etc.)
├── config_flow.py                 # Mode selection (remote/local)
├── coordinator.py                 # Data coordinator (polling/updates)
├── cover.py                       # CoverEntity implementation
└── diagnostic.py                  # Diagnostics (redacted)

exalushome_api/
├── __init__.py
├── models.py                      # Data models (ShutterDevice, etc.)
├── transport.py                   # Abstract Transport interface
├── base.py                        # ExalusShutterAPI abstract class
├── remote.py                      # RemoteShutterAPI implementation
└── local.py                       # LocalShutterAPI implementation
```

---

## 9. First Implementation Order

### Phase 1: Data Models & Transport (2-3 hours)
```python
1. exalushome_api/models.py       # All enums, dataclasses
2. exalushome_api/transport.py    # Abstract Transport interface
3. exalushome_api/base.py         # Abstract ExalusShutterAPI
```

**Validate:** Models match npm package interfaces

### Phase 2: Local Transport (1-2 hours)
```python
1. exalushome_api/local.py        # LocalTransport + LocalShutterAPI
```

**Validate:** Connect to test controller on port 81

### Phase 3: Remote Transport (1-2 hours)
```python
1. exalushome_api/remote.py       # RemoteTransport + RemoteShutterAPI
```

**Validate:** Connect to cloud with test credentials

### Phase 4: HA Config Flow (1-2 hours)
```python
1. custom_components/exalushome/config_flow.py     # Mode selection
2. custom_components/exalushome/const.py           # Constants
3. custom_components/exalushome/__init__.py        # Config entry
```

**Validate:** UI shows both modes, config saves

### Phase 5: HA Cover Entity (1-2 hours)
```python
1. custom_components/exalushome/cover.py           # CoverEntity
2. custom_components/exalushome/coordinator.py     # Data updates
```

**Validate:** Entity creates, position updates

### Phase 6: Package & Distribute (1 hour)
```python
1. custom_components/exalushome/manifest.json
2. custom_components/exalushome/strings.json
3. Documentation
```

**Total: 7-11 hours** (depends on npm package JS-to-Python bindings available)

---

## 10. Validation Checklist Before Coding

### Pre-Implementation (Required)
- [ ] Open https://exalushome.tr7.pl/ in browser
- [ ] Log in with test credentials
- [ ] Open DevTools Network tab, filter XHR
- [ ] Move blind to 0% position
  - Capture `/devices/{id}/state` response
  - Note position value in `IBlindPosition.Data` field
  - Example: If value=0 then 0=open, if value=100 then 100=open
- [ ] Move blind to 50% position
  - Confirm position value reflects midpoint
  - Example: If 0%, 50%, 100% return 0, 50, 100 then scale is 0-100%
- [ ] Move blind to 100% position
  - Capture state response
  - Determine if 0 or 100 means "closed"
- [ ] Click Stop button mid-movement
  - Capture `/devices/{id}/executeTask` POST call
  - Note taskType and Data payload
  - Example: `{ taskType: "SetBlindPositionSimple", data: {...} }`
- [ ] Move blind open fully
  - Capture state to see if TaskExecution or position indicates direction
- [ ] Move blind close fully
  - Capture state to compare with open state
  - Determine if direction can be inferred

### Validation Report Template
```markdown
## Position Scale
- Tested at 0%, 50%, 100%
- Position values: [?, ?, ?]
- Conclusion: [0-100% / 0-255 / 0-180° / other]

## Open vs Close Direction
- Fully open state: position=?
- Fully closed state: position=?
- Conclusion: [0=open / 100=open]

## Stop Command
- API call when Stop clicked: taskType=?, Data={?}
- Conclusion: [SetBlindPositionSimple / other mechanism]

## Movement Direction
- Can distinguish is_opening vs is_closing: [Yes / No / Partial]
- If yes, how: [state field / position tracking / direction flag]
```

### Development Setup (Optional But Recommended)
- [ ] Install pytest for unit tests
- [ ] Create test fixtures for both modes
- [ ] Mock npm package classes if JS bindings unavailable
- [ ] Set up CI/CD pipeline

### Documentation Before Coding
- [ ] Document all Position Scale findings in NARROW_SCOPE_HA_SPEC.md
- [ ] Document Stop Command payload in NARROW_SCOPE_HA_SPEC.md
- [ ] Update README with validated connection flows
- [ ] Create troubleshooting guide for common errors

---

## Summary: Ready to Code After Validation

✅ **Confirmed:**
- Remote mode: ExalusConnectionService (SignalR)
- Local mode: LocalNetworkExalusConnectionService (WebSocket:81)
- Auth: AuthorizationInfo(serial, pin) - same for both
- Frame protocol: IDataFrame (http-like) - same for both
- Entity schema: Device → Channels filtered by Roles
- Commands: SetBlindPosition (POSITION SCALE UNKNOWN)

⏳ **Blocking (2-3 hours web app validation):**
- Position scale (0-100% vs 0-255 vs 0-180°)
- Stop command payload
- Open vs close direction
- Movement state tracking

📋 **Recommended First Task:**
Validate 3 unknowns via web app sniffing → Update NARROW_SCOPE_HA_SPEC.md → Begin Phase 1 (Data Models)
