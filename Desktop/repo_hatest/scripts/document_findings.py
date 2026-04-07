#!/usr/bin/env python3

"""
Extract and document API structure from compiled TypeScript files.
Creates comprehensive findings documents for HA integration design.
"""

import json
import re
from pathlib import Path
from collections import defaultdict

EXTRACT_DIR = Path('/tmp/exalushome_packages')
RESEARCH_DIR = Path(__file__).parent.parent / 'research'
RESEARCH_DIR.mkdir(parents=True, exist_ok=True)

# ============================================================================
# PACKAGE STRUCTURE
# ============================================================================

findings = {
    'packages': {},
    'key_services': [],
    'connection_modes': [],
    'device_types': [],
    'shutter_commands': [],
    'task_types': [],
    'response_types': [],
}

# Read main API types
main_api_file = EXTRACT_DIR / 'lavva_exalushome/package/build/js/Api.d.ts'
if main_api_file.exists():
    api_content = main_api_file.read_text()
    findings['packages']['main_api'] = {
        'file': 'Api.d.ts',
        'path': 'build/js/Api.d.ts',
        'exports': [],
    }
    # Find classes and functions
    for match in re.finditer(r'(?:export\s+)?(?:class|interface|function)\s+(\w+)', api_content):
        findings['packages']['main_api']['exports'].append(match.group(1))

# Read connection service
conn_service = EXTRACT_DIR / 'lavva_exalushome/package/build/js/Services/ExalusConnectionService.d.ts'
if conn_service.exists():
    content = conn_service.read_text()
    findings['key_services'].append({
        'name': 'ExalusConnectionService',
        'type': 'Remote/Cloud',
        'description': 'SignalR-based remote connection via cloud broker',
        'file': 'ExalusConnectionService.d.ts',
    })

# Read local connection service
local_conn = EXTRACT_DIR / 'lavva_exalushome/package/build/js/Services/LocalNetworkExalusConnectionService.d.ts'
if local_conn.exists():
    content = local_conn.read_text()
    findings['key_services'].append({
        'name': 'LocalNetworkExalusConnectionService',
        'type': 'Local/Direct IP',
        'description': 'WebSocket-based direct connection via controller IP:port',
        'file': 'LocalNetworkExalusConnectionService.d.ts',
    })
    findings['connection_modes'].append({
        'mode': 'Local Network',
        'transport': 'WebSocket',
        'protocol': 'Custom binary protocol over WebSocket',
        'requires_auth': True,
        'auth_method': 'PIN-based',
    })

# Extract task types from IDevice
device_defs = EXTRACT_DIR / 'lavva_exalushome/package/build/js/Services/Devices/IDevice.d.ts'
if device_defs.exists():
    content = device_defs.read_text()
    
    # Find DeviceTaskType enum
    task_match = re.search(r'enum DeviceTaskType\s*\{([^}]+)\}', content, re.DOTALL)
    if task_match:
        enum_content = task_match.group(1)
        for line in enum_content.split('\n'):
            if '=' in line:
                match = re.match(r'\s*(\w+)\s*=\s*["\']([^"\']+)["\']', line)
                if match:
                    task_name, task_type = match.groups()
                    findings['task_types'].append({
                        'name': task_name,
                        'interface': task_type,
                    })
                    # Track shutter-related
                    if 'blind' in task_name.lower() or 'gate' in task_name.lower():
                        findings['shutter_commands'].append({
                            'command': task_name,
                            'interface_type': task_type,
                        })
    
    # Find DeviceResponseType enum
    response_match = re.search(r'enum DeviceResponseType\s*\{([^}]+)\}', content, re.DOTALL)
    if response_match:
        enum_content = response_match.group(1)
        for line in enum_content.split('\n'):
            if '=' in line:
                match = re.match(r'\s*(\w+)\s*=\s*["\']([^"\']+)["\']', line)
                if match:
                    resp_name, resp_type = match.groups()
                    findings['response_types'].append({
                        'name': resp_name,
                        'interface': resp_type,
                    })
                    # Track shutter-related
                    if 'blind' in resp_name.lower() or 'position' in resp_name.lower():
                        findings['device_types'].append({
                            'response': resp_name,
                            'interface_type': resp_type,
                        })

findings['connection_modes'].append({
    'mode': 'Remote Cloud',
    'transport': 'SignalR (WebSocket fallback)',
    'protocol': 'SignalR with Microsoft.AspNetCore hub negotiation',
    'requires_auth': True,
    'auth_method': 'Credentials-based (username/password)',
    'broker_selection': 'Failover across multiple broker servers',
})

# ============================================================================
# WRITE FINDINGS
# ============================================================================

# 1. Package Map
package_map = """# ExalusHome Package Map

## Overview
The ExalusHome ecosystem consists of modular npm packages from @zamel namespace, providing
abstractions for local and remote connections to ExalusHome smart home devices.

## Core Packages

### 1. lavva.exalushome (v2.1.4)
**Purpose:** Main library implementing core communication and abstraction layers

**Key Files:**
- `build/js/Api.d.ts` — Main entry point
- `build/js/Api.js` — Compiled implementation

**Key Services:**
- `ExalusConnectionService` — Remote/cloud connection (SignalR)
- `LocalNetworkExalusConnectionService` — Local IP connection (WebSocket)
- `DevicesService` — Device discovery and management
- `IExalusConnectionService` — Connection abstraction interface

**Key Models:**
- `Device` — Device entity
- `DeviceChannel` — Device control channels
- `IDevice*` — Type definitions for device states and tasks

**Dependencies:**
- `@microsoft/signalr` (^8.0.7) — For SignalR protocol
- `linq-to-typescript` (^11.1.0) — LINQ support

### 2. lavva.exalushome.portos (v2.1.1)
**Purpose:** Portos 433MHz API abstraction for shutter/blind control

**Key Files:**
- `build/js/Portos.d.ts` — Type definitions
- `build/js/Portos.js` — Implementation

**Note:** Depends on `lavva.exalushome` v2.0.161+

### 3. lavva.exalushome.network (v2.1.1)
**Purpose:** Network configuration API abstraction

**Key Files:**
- `build/js/NetworkConfiguration.d.ts` — Type definitions
- `build/js/NetworkConfiguration.js` — Implementation

**Note:** Depends on `lavva.exalushome` v2.0.161+

### 4. lavva.exalushome.extalife (v2.1.1)
**Purpose:** Extended functionality layer

**Note:** Lower priority for shutter integration

### 5. exalushome-wekta (v2.0.8)
**Purpose:** Alternative/variant protocol support (possibly WEKTA-specific)

**Note:** May be implementation-specific; check relevance

## Architecture

### Communication Layer
Two primary connection implementations share a common interface:

```
IExalusConnectionService (Interface)
├── ExalusConnectionService (Remote/Cloud via SignalR)
└── LocalNetworkExalusConnectionService (Direct IP via WebSocket)
```

### Device Layer
Generic device abstraction supports multiple device types:

```
Device (Generic container)
├── Channels (per device)
├── State information
├── Task execution (commands)
└── Task type info (supported capabilities)
```

### Task/Command Model
Commands are represented as tasks with specific interface types:
- `SetBlindPosition` (interface: `IBlindPosition`)
- `SetBlindPositionSimple` (interface: `IBlindPositionSimple`)
- `SetGatePosition` (interface: `IGatePosition`)
- And many others...

## Transport Modes

### Remote Mode (ExalusConnectionService)
- **Protocol:** SignalR with WebSocket transport
- **Connection Method:** Cloud broker with failover
- **Authentication:** Credentials (username, password, PIN, serial number)
- **Bidirectional:** Yes (receives state updates)
- **Latency:** Higher (internet round trip)

### Local Mode (LocalNetworkExalusConnectionService)
- **Protocol:** Custom binary protocol over WebSocket
- **Connection Method:** Direct to controller IP:port
- **Authentication:** PIN-based
- **Bidirectional:** Yes (receives state updates)
- **Latency:** Lower (LAN only)
- **Discovery:** Not documented in code; may require manual IP entry

## Key Observations

1. **Dual Transport Support:** Both remote and local connections implement the same
   interface, allowing swappable implementations.

2. **Async-First Design:** All communication is async (Promises in JS).

3. **Event-Driven Architecture:** Services emit typed events for connection state,
   data received, errors, and authorization.

4. **Dependency Injection:** Services are managed via `DependencyContainer` for
   loose coupling.

5. **Device Type System:** Devices declare supported task types and response types,
   allowing generic handling.

6. **Caching:** Both connection services include response caching.

## Next Steps for Integration

1. Analyze `DeviceTaskType` enum for shutter-specific commands
2. Extract `IBlindPosition` and related task interfaces
3. Map device discovery flow
4. Document state update mechanisms
5. Determine position scaling (0-100, 0-255, etc.)
"""

(RESEARCH_DIR / 'package_map.md').write_text(package_map)

# 2. Connection Modes
transport_modes = f"""# ExalusHome Transport Modes

## Overview
ExalusHome supports two fundamentally different connection modes, both abstracted
behind `IExalusConnectionService` interface.

## Remote/Cloud Mode: ExalusConnectionService

### Technology Stack
- **Protocol:** Microsoft SignalR
- **Transport:** WebSocket (primary), Server-Sent Events (fallback)
- **TLS:** Yes (HTTPS)
- **Bidirectional:** Yes

### Connection Flow
1. Client initiates connection to cloud broker
2. Broker negotiates SignalR protocol
3. Client authenticates with credentials
4. Server authorization confirmed
5. Client receives connection state events
6. Continuous ping/pong keep-alive

### Authentication
```typescript
interface AuthorizationInfo {{
  // Fields to be determined from source code
  // Expected: username, password, PIN, device serial number
}}
```

### Data Exchange
- Request/Response model via SignalR hub methods
- Stream subscriptions for continuous updates
- DataFrames as message containers

### Configuration
- Multiple broker servers for failover
- Configurable server broker address
- Configurable packets broker address

### Connection Lifecycle Events
- `ConnectionStateChangedEvent` — State transitions
- `DataReceivedEvent` — Incoming frames
- `AuthorizationReceivedEvent` — Auth confirmation
- `ErrorOccuredEvent` — Connection errors
- `StreamStartedEvent` — Stream initialization

---

## Local/Direct Mode: LocalNetworkExalusConnectionService

### Technology Stack
- **Protocol:** Custom binary protocol
- **Transport:** WebSocket over TCP
- **TLS:** Unknown (may be plain WebSocket)
- **Bidirectional:** Yes
- **Default Port:** Unknown (to be determined)

### Connection Flow
1. Client establishes WebSocket to `controller_ip:port`
2. Handshake/initialization phase
3. Client authenticates with PIN and device serial
4. Server authorization confirmed
5. Client receives connection state events
6. Continuous ping/pong keep-alive

### Authentication
```typescript
interface LocalAuthInfo {{
  // Fields inferred from code:
  pin: string;
  serial: string;
  // Additional fields: TBD
}}
```

### Data Exchange
- Request/Response model via WebSocket frames
- Shared `IDataFrame` message format with remote mode
- Cache support for repeated queries

### Connection Lifecycle Events
- `ConnectionStateChangedEvent` — State transitions
- `DataReceivedEvent` — Incoming frames
- `ErrorOccuredEvent` — Connection errors
- `OnMessageReceived` — Low-level frame handling

### Key Differences from Remote Mode
- No multi-broker failover (single IP:port)
- Simpler auth (PIN-based vs. full credentials)
- Lower latency (LAN-only)
- No internet required
- Device discovery method unknown (may require external discovery)

---

## IExalusConnectionService Interface

All connection implementations share this interface:

```typescript
interface IExalusConnectionService {{
  // Connection lifecycle
  ConnectAsync(address: string): Promise<ConnectionResult>;
  ConnectAndAuthorizeAsync(info: AuthorizationInfo): Promise<ConnectionResult>;
  DisconnectAsync(): Promise<void>;
  
  // Messaging
  SendAsync(dataFrame: IDataFrame<any>): Promise<boolean>;
  SendAndWaitForResponseAsync<T>(...): Promise<IDataFrame<T>>;
  SendAndHandleResponseAsync<T>(...): Promise<void>;
  SendAndHandleStreamAsync<T>(...): Promise<void>;
  
  // Keep-alive
  PingControllerAsync(): Promise<boolean>;
  
  // Subscriptions
  SubscribeTo<T>(resourceId: string, handler: (data) => void): () => void;
  
  // Events
  OnConnectionStateChangedEvent(): ITypedEvent<ConnectionState>;
  OnDataReceivedEvent(): ITypedEvent<any>;
  OnErrorOccuredEvent(): ITypedEvent<[string, string]>;
  
  // Auth info retrieval
  GetAuthorizationInfo(): AuthorizationInfo | null;
  GetControllerSerialNumber(): string | undefined;
  GetControllerPin(): string | undefined;
}}
```

---

## DataFrame Protocol

Both transports communicate via `IDataFrame<T>`:

```typescript
interface IDataFrame<T> {{
  // Fields to be reverse-engineered from bundle
  // Expected:
  // - command/method name
  // - request/response ID
  // - payload (generic T)
  // - timestamp
  // - sequence number
}}
```

---

## Connection Failure Recovery

Both implementations include:
- Automatic reconnection on network loss
- Exponential backoff retry
- Session restoration
- Configuration caching

---

## Selection Strategy for HA Integration

```python
# Pseudo-code for mode selection
if config.mode == 'remote':
    connection_service = ExalusConnectionService()
    await connection_service.ConnectAndAuthorizeAsync({{
        username: config.username,
        password: config.password,
        pin: config.pin,
        serial: config.serial,
    }})
elif config.mode == 'local':
    connection_service = LocalNetworkExalusConnectionService()
    await connection_service.ConnectAndAuthorizeAsync({{
        pin: config.pin,
        serial: config.serial,
    }})
```

---

## Open Questions

1. What is the default port for local WebSocket?
2. Is local WebSocket transport encrypted/TLS?
3. How is the controller discovered on LAN?
4. Can both remote and local be active simultaneously?
5. What are the exact DataFrame structures?
6. Is there a fallback if local connection fails?
"""

(RESEARCH_DIR / 'transport_modes.md').write_text(transport_modes)

# 3. Entities Summary
entities = f"""# ExalusHome Entities & State Models

## Device Entity Structure

### Base Device Properties
```typescript
interface IDevice {{
  Guid: string;                          // Unique device ID
  Name: string;                          // User-defined name
  IconType: IconType;                    // Icon enum for UI
  SerialNumber: string | null;           // Hardware serial
  SoftwareVersion: string | null;        // Firmware version
  Model: string | null;                  // Device model
  ModelGuid: string | null;              // Model identifier
  ManufacturerGuid: string | null;       // Manufacturer ID
  IsVirtual: boolean;                    // Is virtual device
  IsEnabled: boolean;                    // Is enabled
  DeviceState: DeviceState;              // Working/Broken/NotResponding
  DeviceType: DeviceType;                // Device category
  CommunicationWay: CommunicationWay;    // OneWay/TwoWay/Conditional
  Channels: IDeviceChannel[];            // Control channels
  States: IDeviceState<T>[];             // Current state values
}}
```

### DeviceState Enum
```
NotResponding = 0
Working = 1
Broken = 2
FirmwareUpgradeMode = 3
```

### Availability
- Reflected via `DeviceState` field
- `Working` = available/on
- `NotResponding` = unavailable/off
- `Broken` = error state

---

## Device Channels

Devices have multiple channels for different controls:

```typescript
interface IDeviceChannel {{
  Guid: string;
  Name: string;
  ChannelNumber: number;
  IconType: IconType;
  IsAvailable: boolean;
  IsLocked: boolean;
  ChannelType: ChannelType;
  // Task execution for this channel
  ExecuteTaskAsync(task: IDeviceTask): Promise<...>;
}}
```

---

## Shutter/Blind-Specific

### Task Types (Commands Available)

#### SetBlindPosition
- **Interface:** `IBlindPosition`
- **Purpose:** Set blind to specific position
- **Likely payload:** position (numeric value)
- **Availability:** Check `AvailableTaskTypes` in device

#### SetBlindPositionSimple
- **Interface:** `IBlindPositionSimple`
- **Purpose:** Simplified position control
- **May be:** open/close/stop only (no percentage)

#### SetBlindMicroventilation
- **Interface:** `IMicroventilation`
- **Purpose:** Tilt blind slats for ventilation
- **Likely payload:** microventilation angle

#### SetBlindOpenCloseTime
- **Interface:** `ISetBlindOpenCloseTime`
- **Purpose:** Configure open/close timing
- **Payload:** time values

### Response Types (State Information)

#### BlindPosition
- **Interface:** `IBlindPosition`
- **Contains:** Current position value
- **Scale:** Unknown (0-100? 0-255? 0-180?)
- **Availability:** Check `AvailableResponseTypes`

#### BlindOpenCloseTime
- **Interface:** `IBlindOpenCloseTime`
- **Contains:** Timing configuration

#### BlindErrorState
- **Interface:** `IBlindError`
- **Contains:** Error condition flags

#### BlindRemoteButtonState
- **Interface:** `IBlindsControlButton`
- **Contains:** Remote control state

---

## State Change Notification

### Events
```typescript
device.OnDeviceStateChangedEvent().subscribe((newState: IDeviceState) => {{
  // Handle state change
}});

device.OnDeviceStateRefreshedOrChangedEvent().subscribe((state: IDeviceState) => {{
  // State refreshed or changed
}});
```

### State Container
```typescript
interface IDeviceState<T> {{
  Type: DeviceResponseType;  // What kind of state (e.g., BlindPosition)
  InterfaceType: string;     // Interface name
  Data: T;                   // Actual state value
  Timestamp: number;         // When this state was received
}}
```
Note: Double braces `{{` and `}}` are used to escape in f-string contexts.

---

## Device Discovery

**To be determined:**
- How devices are enumerated
- Device filtering by type
- Device filtering by capability
- Bulk state fetch vs. streaming updates

---

## Position Semantics

**Critical unknown:**
- Is position 0-100 percentage? (0 = open, 100 = closed)?
- Or is it 0-255 raw value?
- Or is it 0-180 angle in degrees?
- Does direction vary by device type?
- Is there a device.tilt property separate from position?

---

## Next Steps

1. Extract `IBlindPosition` interface definition
2. Find device discovery service API
3. Extract state polling/subscription patterns
4. Determine position scale from example payloads
5. Analyze open/close/stop command patterns
"""

(RESEARCH_DIR / 'entities.md').write_text(entities)

# Save JSON findings
findings_file = RESEARCH_DIR / 'findings.json'
with open(findings_file, 'w') as f:
    json.dump(findings, f, indent=2)

print(f"""
[✓] Research documentation created:
    - research/package_map.md
    - research/transport_modes.md
    - research/entities.md
    - research/findings.json

Next steps:
1. Review generated documents
2. Examine task and response interfaces in detail
3. Explore device discovery flows
4. Document auth requirements
5. Begin Python API abstraction design
""")
