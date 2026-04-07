# ExalusHome HA Integration — Implementation Starter

## Quick Reference

### Documents Generated

1. **package_map.md** — Package architecture and responsibilities
2. **transport_modes.md** — Remote (SignalR) vs Local (WebSocket) protocols
3. **auth_remote.md** — Cloud authentication and remote connection details
4. **auth_local.md** — Local network auth and WebSocket port 81 discovery
5. **entities.md** — Device and state entity models
6. **commands.md** — Shutter task types and execution model
7. **ha_integration_spec.md** — Full HA integration design (21KB)

### Key Findings

#### Connection Information

**Remote Mode (Cloud):**
- Protocol: Microsoft SignalR
- Broker: exalushome.tr7.pl (inferred)
- Auth: AuthorizationInfo(serial_number, pin)
- DataFrame: { Resource?, TransactionId?, Data?, Status?, Method? }

**Local Mode (Direct IP):**
- Protocol: WebSocket over TCP
- Port: 81 (default, fixed)
- Auth: AuthorizationInfo(serial_number, pin) — same as remote
- DataFrame: Same as remote
- HTTP Endpoint: `http://controller_ip/controller_info` returns `SERIAL:PIN`

#### Device Models

**Device (IDevice):**
- Guid: Unique identifier
- Name: User-friendly name
- State: DeviceState (Working, NotResponding, Broken, FirmwareUpgradeMode)
- Channels: Array of control channels
- Model, ModelGuid, SerialNumber, etc.

**Channel (IDeviceChannel):**
- ChannelId, Number, Name
- Roles: Includes Blind(11), Roller(12), BlindsWithPrecisePosition(21)
- AvailableTaskTypes: What commands are supported
- AvailableResponseTypes: What state types are available

**State (IDeviceState<T>):**
- Type: DeviceResponseType (BlindPosition, BlindError, etc.)
- Data: Generic payload
- Timestamp: When state was captured

#### Shutter Commands

**Primary Task:**
- SetBlindPosition (interface: IBlindPosition)
- Payload: position value
- Scale: **UNKNOWN — MUST VALIDATE** (0-100%, 0-255, 0-180 degrees?)

**Secondary Tasks:**
- SetBlindPositionSimple (simplified control)
- SetBlindMicroventilation (tilt blinds)
- SetBlindOpenCloseTime (calibration)

**Stop Command:**
- Mechanism unclear — likely via SetBlindPositionSimple or special value

---

## Validation Checklist

### Critical (Must Resolve Before Implementation)

- [ ] **Position Scale:** Extract exact min/max position values from web app API
  - Method: Sniff API calls while moving blind to known percentages
  - Expected: Find if 0-100, 0-255, 0-180, or device-specific
  
- [ ] **Stop Command:** Determine how to stop blind mid-movement
  - Method: Look for SetBlindPositionSimple payload structure
  - Expected: Find enum value or method name for "stop"
  
- [ ] **Local Device Discovery:** How does official app find controllers on LAN?
  - Method: Network analysis (check for mDNS broadcasts, UDP discovery)
  - Expected: Find automatic or manual discovery mechanism
  
- [ ] **Controller Availability:** What indicates online/offline/error state?
  - Method: Analyze DeviceState usage in app
  - Expected: Confirm NotResponding → unavailable mapping

### Important (Should Resolve)

- [ ] **Firmware Version Field:** Confirm field name and format
- [ ] **Task Execution Status:** What are the exact DeviceTaskExecutionResult values?
- [ ] **State Update Mechanism:** Is it polling, push, or both?
- [ ] **Multi-Channel Handling:** How are multi-blind devices exposed to user?
- [ ] **Error Codes:** What do Status enum values mean?
- [ ] **Microventilation Range:** What are valid angles/values?

### Nice-to-Have (Can Work Around If Needed)

- [ ] **Room/Group Assignment:** Do devices have location metadata?
- [ ] **Custom Naming Rules:** User conventions for device names?
- [ ] **Cloud Broker Failover:** What are backup broker addresses?
- [ ] **SignalR Hub Path:** Exact connection endpoint path?

---

## Validation Method: Web App Sniffing

### Setup
1. Open https://exalushome.tr7.pl/ in browser
2. Open DevTools (F12) → Network tab
3. Filter: `XHR` and `WS` (WebSocket)
4. Log in with credentials
5. Perform test actions:
   - Move blind to 0% (fully open)
   - Move blind to 50% (half)
   - Move blind to 100% (fully closed)
   - Try to stop mid-movement
   - Check device list API response

### Expected Findings

**Device List Response:**
```json
{
  "devices": [
    {
      "guid": "...",
      "name": "Living Room Blind",
      "model": "...",
      "state": "working",
      "position": 75,
      "channels": [...]
    }
  ]
}
```

**Position Command Request:**
```json
{
  "resource": "/devices/abc123/executeTask",
  "method": "post",
  "data": {
    "taskType": "IBlindPosition",
    "position": 50  // This is what we need to validate!
  }
}
```

**State Update Response:**
```json
{
  "resource": "/devices/abc123/state",
  "data": {
    "states": [
      {
        "type": "IBlindPosition",
        "value": 75
      }
    ]
  }
}
```

---

## Implementation Starter Code

### Project Structure
```
custom_components/exalushome/
├── __init__.py
├── const.py
├── config_flow.py
├── coordinator.py
├── manifest.json
├── cover.py
└── api/
    ├── base.py
    ├── remote.py
    └── local.py
```

### Quick Start: const.py
```python
"""Constants for ExalusHome integration."""

DOMAIN = "exalushome"
PLATFORMS = ["cover"]

CONF_CONNECTION_MODE = "connection_mode"
CONF_MODE_REMOTE = "remote"
CONF_MODE_LOCAL = "local"
CONF_MODE_DUAL = "dual"

CONF_REMOTE_USERNAME = "username"
CONF_REMOTE_PASSWORD = "password"
CONF_LOCAL_HOST = "host"
CONF_LOCAL_PORT = "port"

CONF_SERIAL_NUMBER = "serial_number"
CONF_PIN = "pin"

DEFAULT_PORT = 81
DEFAULT_UPDATE_INTERVAL = 30  # seconds

# Device Type Constants
ICON_TYPE_BLIND_MOTOR = 1  # From IDevice enum

# Roles indicating blinds/shutters
BLIND_ROLES = {11, 12, 21, 23}  # Blind, Roller, BlindsWithPrecisePosition, BlindsRemote

# Task Types for Blind Control
TASK_SET_BLIND_POSITION = "SetBlindPosition"
TASK_SET_BLIND_POSITION_SIMPLE = "SetBlindPositionSimple"
TASK_MICROVENTILATION = "SetBlindMicroventilation"

# Response Types
RESPONSE_BLIND_POSITION = "BlindPosition"
RESPONSE_BLIND_ERROR = "BlindErrorState"
```

### Quick Start: manifest.json
```json
{
  "domain": "exalushome",
  "name": "ExalusHome",
  "codeowners": ["@GrubyRabbit"],
  "config_flow": true,
  "documentation": "https://github.com/GrubyRabbit/exalushome-ha",
  "requirements": [],
  "version": "0.1.0"
}
```

### Quick Start: base.py (API Abstraction)
```python
"""Base API abstraction for ExalusHome."""
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import List

@dataclass
class Device:
    """ExalusHome device."""
    guid: str
    name: str
    model: str | None
    state: str  # working, notresponding, broken
    serial_number: str | None = None

@dataclass
class DeviceState:
    """Device state."""
    device_guid: str
    position: int | None = None  # Blind position (scale TBD)
    available: bool = True

class ExalusAPIBase(ABC):
    """Base class for ExalusHome API implementations."""
    
    @abstractmethod
    async def connect(self) -> bool:
        """Connect to ExalusHome."""
        pass
    
    @abstractmethod
    async def disconnect(self) -> None:
        """Disconnect from ExalusHome."""
        pass
    
    @abstractmethod
    async def get_devices(self) -> List[Device]:
        """Get list of all devices."""
        pass
    
    @abstractmethod
    async def get_device_state(self, device_guid: str) -> DeviceState:
        """Get current state of a device."""
        pass
    
    @abstractmethod
    async def set_blind_position(self, device_guid: str, position: int) -> bool:
        """Set blind to specific position (0-100 or 0-255?)."""
        pass
    
    @abstractmethod
    async def stop_blind(self, device_guid: str) -> bool:
        """Stop blind movement."""
        pass
```

### Quick Start: remote.py
```python
"""Remote/Cloud connection implementation."""
from .base import ExalusAPIBase, Device, DeviceState

class RemoteAPI(ExalusAPIBase):
    """ExalusHome cloud connection via SignalR."""
    
    def __init__(self, username: str, password: str, serial: str, pin: str):
        self.username = username
        self.password = password
        self.serial = serial
        self.pin = pin
        self.connection = None
        # Import from npm bundle would go here
        # For now: assume js.Api.ExalusConnectionService available
    
    async def connect(self) -> bool:
        """Connect via SignalR to cloud broker."""
        # Step 1: Create connection service
        # Step 2: Call ConnectAndAuthorizeAsync()
        # Step 3: Return success/failure
        pass
    
    async def get_devices(self) -> list[Device]:
        """Fetch devices from cloud."""
        # Send DataFrame with Resource="/devices"
        # Parse response, extract device list
        # Return list of Device objects
        pass
```

### Quick Start: local.py
```python
"""Local network connection implementation."""
from .base import ExalusAPIBase, Device, DeviceState

class LocalAPI(ExalusAPIBase):
    """ExalusHome local network connection via WebSocket."""
    
    def __init__(self, host: str, port: int, serial: str, pin: str):
        self.host = host
        self.port = port
        self.serial = serial
        self.pin = pin
        self.connection = None
    
    async def connect(self) -> bool:
        """Connect via WebSocket to controller on port 81."""
        # Step 1: Create WebSocket connection to ws://host:81
        # Step 2: Send AuthorizationInfo(serial, pin)
        # Step 3: Wait for authorization response
        # Step 4: Return success/failure
        pass
    
    async def get_devices(self) -> list[Device]:
        """Fetch devices from local controller."""
        # Send DataFrame with Resource="/devices"
        # Parse response, extract device list
        # Return list of Device objects
        pass
```

---

## Next Steps

1. **Validate Critical Unknowns**
   - Use web app sniffing to determine position scale
   - Test with real hardware if available
   - Document findings in gaps_for_web_validation.md

2. **Implement Python Wrapper**
   - Decide on JS/Python bridge (node-pyenv? subprocess? other?)
   - Or re-implement protocol from source code analysis

3. **Develop Integration**
   - Start with remote mode (simpler, no local network needed for testing)
   - Then add local mode
   - Then add dual/fallback

4. **Test Coverage**
   - Unit tests for protocol handling
   - Integration tests with mock coordinator
   - Real hardware testing if controller available

5. **Documentation & Distribution**
   - Prepare HACS integration package
   - Document setup and troubleshooting
   - Create GitHub repository

---

## Resources

### Source Code Available At
- `/tmp/exalushome_packages/` (extracted npm packages)
- Compile TypeScript: `find /tmp/exalushome_packages -name "*.d.ts"` (type definitions)

### Official Resources
- ExalusHome Web App: https://exalushome.tr7.pl/
- npm Packages: https://www.npmjs.com/~zamel

### HA Integration Resources
- Custom Component Dev: https://developers.home-assistant.io/docs/creating_component_index
- CoverEntity: https://developers.home-assistant.io/docs/core/entity/cover/
- Config Flow: https://developers.home-assistant.io/docs/configuration_flow_index/

---

## Questions & Support

This research document was generated through reverse engineering of ExalusHome npm packages.
Validation against real hardware and the official web app is required before production use.

Key unknowns still require web app analysis or direct hardware testing.
See validation checklist above for critical items before starting implementation.
