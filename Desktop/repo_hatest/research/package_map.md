# ExalusHome Package Map

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
