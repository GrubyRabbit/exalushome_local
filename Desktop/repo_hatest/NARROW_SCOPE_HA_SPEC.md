# Home Assistant Roller Shutter Integration - Narrow Scope

**Focus:** Home Assistant `cover` platform for ExalusHome roller shutters only  
**Scope:** Minimal viable implementation  
**Last Updated:** 2026-04-07

---

## 1. Remote Mode Confirmation ✅

**CONFIRMED:** Remote mode exists and is production-ready.

```typescript
// Class: ExalusConnectionService (implements IExalusConnectionService)
// Location: lavva.exalushome v2.1.4
// Protocol: Microsoft SignalR
// Transport: WebSocket
// Broker: exalushome.tr7.pl (inferred)

class ExalusConnectionService implements IExalusConnectionService {
    ConnectAndAuthorizeAsync(info: AuthorizationInfo): Promise<ConnectionResult>
    SendAndWaitForResponseAsync<T>(frame: IDataFrame<any>, timeout, useCache): Promise<IDataFrame<T>>
    OnConnectionStateChangedEvent(): ITypedEvent<ConnectionState>
}
```

**Auth Requirements:**
```typescript
class AuthorizationInfo {
    serialNumber: string;  // Controller serial number
    pin: string;          // Controller PIN
}
```

**Connection Flow:**
1. Create `AuthorizationInfo(serialNumber, pin)`
2. Call `ConnectAndAuthorizeAsync(authInfo)` → returns `ConnectionResult.Connected`
3. Send/receive `IDataFrame<T>` payloads
4. Subscribe to state updates or poll

---

## 2. Local/Direct-IP Mode Confirmation ✅

**CONFIRMED:** Local direct-IP mode exists and is production-ready.

```typescript
// Class: LocalNetworkExalusConnectionService (implements IExalusConnectionService)
// Location: lavva.exalushome v2.1.4
// Protocol: Custom binary over WebSocket
// Port: 81 (hardcoded)
// Transport: ws://controller_ip:81/

class LocalNetworkExalusConnectionService implements IExalusConnectionService {
    ConnectAndAuthorizeAsync(info: AuthorizationInfo): Promise<ConnectionResult>
    SendAndWaitForResponseAsync<T>(frame: IDataFrame<any>, timeout, useCache): Promise<IDataFrame<T>>
    OnConnectionStateChangedEvent(): ITypedEvent<ConnectionState>
}
```

**Key Findings:**
- Same `AuthorizationInfo(serialNumber, pin)` as remote
- Validation endpoint: `http://controller_ip/controller_info` returns `SERIAL:PIN`
- Keep-alive: `/system/ping` endpoint
- Limitation: Streams not supported (only polling)

**Connection Flow:**
1. WebSocket connection to `ws://controller_ip:81/`
2. Create `AuthorizationInfo(serialNumber, pin)`
3. Call `ConnectAndAuthorizeAsync(authInfo)` → returns `ConnectionResult.Connected`
4. Send/receive `IDataFrame<T>` payloads (polling only, no streams)

---

## 3. Shutter Entity Schema ✅

### Device Structure
```typescript
interface IDevice {
    Guid: string;                      // Unique ID (use for entity_id)
    Name: string;                      // User-friendly name
    State: DeviceState;                // Working | NotResponding | Broken | FirmwareUpgradeMode
    Model: string | null;
    SerialNumber: string | null;
    Channels: IDeviceChannel[];        // Array of control channels
}
```

### Channel Structure (Per Shutter)
```typescript
interface IDeviceChannel {
    ChannelId: string;
    Number: number;
    Name: string;                      // e.g., "Living Room Blind"
    Roles: Roles[];                    // [Blind=11, Roller=12, BlindsWithPrecisePosition=21, ...]
    States: IDeviceState<IDeviceStateData>[];    // Current state values
    AvailableTaskTypes: IDeviceTaskTypeInfo[];   // What commands this channel supports
    AvailableResponseTypes: IDeviceResponseTypeInfo[];  // What state types it reports
    ExecuteTaskAsync(task: IDeviceTask): Promise<DeviceTaskExecutionResult>
}
```

### Filtering for Shutters
```python
# Include channel if Roles contains any of:
SHUTTER_ROLES = {11, 12, 21, 23}  # Blind, Roller, BlindsWithPrecisePosition, BlindsRemote

# Skip channel if it has unrelated roles (lights, switches, sensors, etc.)
```

---

## 4. Position & State Fields ✅

### State Information
```typescript
interface IDeviceState<T> {
    Type: DeviceResponseType;   // What kind of state (BlindPosition, BlindError, etc.)
    Data: T;                    // Actual value
}

enum DeviceResponseType {
    BlindPosition = "IBlindPosition",           // Current position (SCALE UNKNOWN - see unknowns)
    BlindOpenCloseTime = "IBlindOpenCloseTime", // Timing calibration
    BlindErrorState = "IBlindError",            // Error flags
    BlindRemoteButtonState = "IBlindsControlButton",  // Remote control state
}
```

### Availability
```python
# Map from IDevice.State:
DeviceState.Working → available=True
DeviceState.NotResponding → available=False
DeviceState.Broken → available=False
DeviceState.FirmwareUpgradeMode → available=False
```

### Movement Tracking
```typescript
enum TaskExecution {
    NoTasksExecuting = 0,
    ExecutingTasks = 1,
}

// Subscribe to channel state changes:
channel.OnChannelStateChangedEvent().subscribe((state: IDeviceState) => {
    // state contains new position/status
});

// Check if moving:
channel.OnTasksExecutionChangeEvent().subscribe((execution: TaskExecution) => {
    if (execution === TaskExecution.ExecutingTasks) {
        // Blind is moving (opening/closing)
    }
});
```

---

## 5. Command Mapping ✅

### Available Commands

#### Open (Move to max open position)
```typescript
// Command
const task: IDeviceTask = {
    Type: DeviceTaskType.SetBlindPosition,
    Data: { position: ??? }  // Unknown: 0 or 100? Validate needed.
};
await channel.ExecuteTaskAsync(task);

// Response
Result: DeviceTaskExecutionResult
```

#### Close (Move to fully closed position)
```typescript
const task: IDeviceTask = {
    Type: DeviceTaskType.SetBlindPosition,
    Data: { position: ??? }  // Unknown: 100 or 0? Validate needed.
};
await channel.ExecuteTaskAsync(task);
```

#### Set Exact Position (0-100%)
```typescript
const task: IDeviceTask = {
    Type: DeviceTaskType.SetBlindPosition,
    Data: { position: 50 }  // Assuming 0-100 scale (VALIDATE)
};
await channel.ExecuteTaskAsync(task);
```

#### Stop Movement
```typescript
// Option 1: SetBlindPositionSimple (likely)
const task: IDeviceTask = {
    Type: DeviceTaskType.SetBlindPositionSimple,
    Data: { /* unknown structure */ }
};
await channel.ExecuteTaskAsync(task);

// Option 2: Unknown - REQUIRES VALIDATION
```

### Command Capability Detection
```python
# Before executing a command, check if channel supports it:
for task_type_info in channel.AvailableTaskTypes:
    if task_type_info.Type == DeviceTaskType.SetBlindPosition:
        # Device supports exact position control
        supports_position = True
    if task_type_info.Type == DeviceTaskType.SetBlindPositionSimple:
        # Device supports simplified control (open/close/stop)
        supports_simple = True

# Only expose commands that are actually available
```

---

## 6. Protocol & Payload Structure ✅

### Universal Frame Format (Both Modes)
```typescript
interface IDataFrame<T> {
    Resource?: string;        // API endpoint path (e.g., "/devices/abc123/state")
    TransactionId?: string;   // Request ID for matching request-response
    Data?: T;                 // Payload (varies by Resource type)
    Status?: Status;          // Response status (0=OK, 1-16 various errors)
    Method?: Method;          // HTTP-like method (0=Get, 1=Post, etc.)
}

enum Status {
    OK = 0,
    UnknownError = 1,
    FatalError = 2,
    WrongData = 3,
    ResourceDoesNotExists = 4,
    NoPermissionToPerformThisOperation = 5,
    UserIsNotLoggedIn = 13,
    // ... others
}

enum Method {
    Get = 0,
    Post = 1,
    Delete = 2,
    Put = 3,
}
```

### Sending a Command
```python
request = IDataFrame(
    Resource="/devices/{device_guid}/executeTask",
    TransactionId="req_001",
    Method=Method.Post,  # 1
    Data={
        "taskType": "IBlindPosition",
        "position": 50
    }
)

response = await connection_service.SendAndWaitForResponseAsync(
    request,
    timeout=5000,  # milliseconds
    useCache=False
)

# Check response
if response.Status == Status.OK:  # 0
    # Command accepted
    result = response.Data
else:
    # Error - see Status code
    error = response.Status
```

### Getting State
```python
request = IDataFrame(
    Resource="/devices/{device_guid}/state",
    Method=Method.Get,  # 0
)

response = await connection_service.SendAndWaitForResponseAsync(
    request,
    timeout=5000,
    useCache=True
)

# response.Data contains state object with current position, errors, etc.
```

---

## 7. Recommended HA Architecture ✅

### Python API Layer (Abstract Both Modes)

**File: `exalushome_api/base.py`**
```python
from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum

class ConnectionMode(Enum):
    REMOTE = "remote"
    LOCAL = "local"

@dataclass
class ShutterDevice:
    guid: str
    name: str
    model: str | None
    available: bool  # From DeviceState
    position: int | None  # Current position (0-100, scale unknown - VALIDATE)
    is_moving: bool
    supports_exact_position: bool

@dataclass
class ShutterCommand:
    device_guid: str
    action: str  # "open", "close", "stop", "set_position"
    position: int | None = None  # For set_position action

class ExalusShutterAPI(ABC):
    """Abstract base for both remote and local modes."""
    
    @abstractmethod
    async def connect(self) -> bool:
        """Connect and authorize."""
        pass
    
    @abstractmethod
    async def disconnect(self) -> None:
        pass
    
    @abstractmethod
    async def get_shutters(self) -> list[ShutterDevice]:
        """Get all shutter channels across all devices."""
        pass
    
    @abstractmethod
    async def get_shutter_state(self, device_guid: str, channel_id: str) -> ShutterDevice:
        """Get current state of one shutter."""
        pass
    
    @abstractmethod
    async def execute_command(self, cmd: ShutterCommand) -> bool:
        """Execute open/close/stop/set_position command."""
        pass

class RemoteShutterAPI(ExalusShutterAPI):
    """SignalR-based cloud implementation."""
    
    def __init__(self, username: str, password: str, serial: str, pin: str):
        self.connection_service = ExalusConnectionService()
        # Implement abstract methods using ExalusConnectionService
        pass

class LocalShutterAPI(ExalusShutterAPI):
    """WebSocket-based direct IP implementation."""
    
    def __init__(self, host: str, port: int, serial: str, pin: str):
        self.connection_service = LocalNetworkExalusConnectionService()
        # Implement abstract methods using LocalNetworkExalusConnectionService
        pass
```

### Home Assistant Integration Structure

**File: `custom_components/exalushome/cover.py`**
```python
from homeassistant.components.cover import CoverEntity, CoverEntityFeature

class ExalusHomeCover(CoverEntity):
    """Representation of ExalusHome roller shutter."""
    
    def __init__(self, api: ExalusShutterAPI, device_guid: str, channel_id: str):
        self.api = api
        self.device_guid = device_guid
        self.channel_id = channel_id
        self._attr_unique_id = f"exalushome_{device_guid}_{channel_id}"
    
    @property
    def current_cover_position(self) -> int | None:
        """Return position 0-100 (0=open, 100=closed)."""
        return self._device.position
    
    @property
    def is_opening(self) -> bool:
        """Return True if cover is currently opening."""
        return self._device.is_moving  # Need to distinguish open vs close
    
    @property
    def is_closing(self) -> bool:
        """Return True if cover is currently closing."""
        return self._device.is_moving  # Need to distinguish open vs close
    
    @property
    def is_closed(self) -> bool:
        """Return True if closed."""
        return self._device.position == 100  # Assuming 100=closed
    
    @property
    def available(self) -> bool:
        """Return True if device is online."""
        return self._device.available
    
    @property
    def supported_features(self) -> CoverEntityFeature:
        """Return supported features."""
        features = (
            CoverEntityFeature.OPEN |
            CoverEntityFeature.CLOSE |
            CoverEntityFeature.STOP
        )
        if self._device.supports_exact_position:
            features |= CoverEntityFeature.SET_POSITION
        return features
    
    async def async_open_cover(self, **kwargs):
        """Open the cover."""
        cmd = ShutterCommand(self.device_guid, "open")
        await self.api.execute_command(cmd)
    
    async def async_close_cover(self, **kwargs):
        """Close the cover."""
        cmd = ShutterCommand(self.device_guid, "close")
        await self.api.execute_command(cmd)
    
    async def async_stop_cover(self, **kwargs):
        """Stop the cover."""
        cmd = ShutterCommand(self.device_guid, "stop")
        await self.api.execute_command(cmd)
    
    async def async_set_cover_position(self, **kwargs):
        """Set cover to specific position."""
        position = kwargs.get("position")  # 0-100
        cmd = ShutterCommand(self.device_guid, "set_position", position)
        await self.api.execute_command(cmd)
```

### Configuration Flow
```python
# custom_components/exalushome/config_flow.py

class ExalusHomeConfigFlow(ConfigFlow, domain=DOMAIN):
    
    async def async_step_user(self, user_input=None):
        """Handle user-initiated config."""
        if user_input is None:
            return self.async_show_form(
                step_id="user",
                data_schema=vol.Schema({
                    vol.Required("mode"): vol.In(["remote", "local"]),
                })
            )
        
        if user_input["mode"] == "remote":
            return await self.async_step_remote()
        else:
            return await self.async_step_local()
    
    async def async_step_remote(self, user_input=None):
        """Configure remote/cloud mode."""
        if user_input is None:
            return self.async_show_form(
                step_id="remote",
                data_schema=vol.Schema({
                    vol.Required("username"): str,
                    vol.Required("password"): str,
                    vol.Required("serial_number"): str,
                    vol.Required("pin"): str,
                })
            )
        # Validate and save
    
    async def async_step_local(self, user_input=None):
        """Configure local mode."""
        if user_input is None:
            return self.async_show_form(
                step_id="local",
                data_schema=vol.Schema({
                    vol.Required("host"): str,
                    vol.Required("port", default=81): int,
                    vol.Required("serial_number"): str,
                    vol.Required("pin"): str,
                })
            )
        # Validate and save
```

---

## 8. Unknowns Requiring Web App Validation

### Critical (Blocks Implementation)

1. **Position Scale**
   - Question: What are valid position values?
   - Options:
     - 0-100 (percentage)
     - 0-255 (8-bit raw)
     - 0-180 (angle in degrees)
     - Device-specific calibrated values
   - How to validate: Use web app to move blind to 0%, 25%, 50%, 75%, 100% and capture API payloads
   - What to look for: Position values in `/devices/{id}/state` responses
   - Impact: HIGH (affects HA open/close direction mapping)

2. **Open vs Close Direction**
   - Question: Does position 0 mean open or closed?
   - How to validate: Move blind fully open and check state, then fully close and check state
   - Impact: HIGH (affects CoverEntity.is_open/is_closed logic)

3. **Stop Command Mechanism**
   - Question: How to stop blind mid-movement?
   - Options:
     - Use `SetBlindPositionSimple` with special value
     - Dedicated task type
     - Send current position as hold command
   - How to validate: In web app, start blind movement, then click stop button, capture API call
   - Impact: MEDIUM (affects CoverEntity.STOP feature)

### Important (Improves Implementation)

4. **Movement State Reporting**
   - Question: How to distinguish opening vs closing?
   - Current info: `TaskExecution` flag indicates "moving" but not direction
   - How to validate: Move blind open, capture state; move blind closed, capture state
   - Impact: MEDIUM (affects `is_opening`/`is_closing` properties)

5. **State Update Frequency**
   - Question: How often does position update? Push or polling?
   - How to validate: Move blind and monitor web app real-time updates
   - Impact: LOW (affects coordinator polling interval, can use sensible default)

---

## Summary: Cleanest Python Abstraction

**Single interface hiding both modes:**

```python
class ExalusShutterAPI(ABC):
    """Universal API for remote and local modes."""
    
    async def connect(self) -> bool: pass
    async def get_shutters(self) -> list[ShutterDevice]: pass
    async def get_shutter_state(self, device_guid, channel_id) -> ShutterDevice: pass
    async def execute_command(self, cmd: ShutterCommand) -> bool: pass
```

**HA Integration:**
- Create `ExalusShutterAPI` subclass based on config (remote/local)
- Pass to coordinator and entity
- Entities know nothing about connection mode
- Easy to add fallback (try local, fall back to remote) later

**Files to implement:**
1. `exalushome_api/base.py` — Abstract API
2. `exalushome_api/remote.py` — SignalR implementation
3. `exalushome_api/local.py` — WebSocket implementation
4. `custom_components/exalushome/cover.py` — HA CoverEntity
5. `custom_components/exalushome/config_flow.py` — Config UI

---

## Implementation Ready: 70%

✅ Both remote and local modes confirmed in npm packages  
✅ Shutter entity schema mapped  
✅ Position/state fields identified  
✅ Commands identified (open/close/stop/set_position)  
✅ Clean abstraction layer designed  

⚠️ Need validation (2-3 hours web app analysis):
- Position scale (0-100%, 0-255, 0-180°?)
- Stop command mechanism
- Open vs close direction
- Movement state reporting

**Recommended next:** Sniff web app API with browser DevTools (see Unknowns section 1-3) to unlock implementation.
