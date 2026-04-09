# ExalusHome Local Integration - Implementation Notes

## Overview

This is a Home Assistant custom integration for ExalusHome roller shutters/blinds using **local direct IP connection** via WebSocket on port 81.

**Status:** Initial skeleton implementation based on validated protocol findings.

---

## Implemented Protocol Details

### Connection
- **Protocol:** WebSocket over TCP
- **Host:** Local controller IP address (user-provided)
- **Port:** 81 (hardcoded in ExalusHome controller)
- **URL:** `ws://{host}:81/`
- **TLS/SSL:** None (plain WebSocket)

### Authentication
- **Mechanism:** Credential-based (serial number + PIN)
- **Credentials:**
  - `serial_number`: Controller serial number (e.g., "ABC123DEF456")
  - `pin`: Controller PIN (default "0000", user-configurable)
- **Validation:** Sent as JSON on connection

### Blind Control Commands

Commands sent as JSON over WebSocket with structure:
```json
{
  "type": "DataFrameCommand",
  "resource": "/devices/device/control",
  "data": {
    "device": "{device_guid}",
    "channel": {channel_number},
    "control": {command_code}
  }
}
```

**Command Codes:**
- `101` - Open (move to fully open position)
- `102` - Close (move to fully closed position)  
- `103` - Stop (halt current movement)
- `0-100` - Set exact position (Exalus scale)

### State Tracking

Device state updates received as WebSocket events:
```json
{
  "type": "DeviceStateChanged",
  "data": { ... }
}
```

**Critical Field:** `TaskExecution`
- `0` = Not moving
- `1` = Currently moving (but cannot distinguish open vs close)

### Position Scale (Validated)

**Exalus Position Scale:**
- `0` = Fully OPEN
- `100` = Fully CLOSED
- `1-99` = Partially open

**Home Assistant Position Scale:**
- `0` = Fully CLOSED
- `100` = Fully OPEN
- `1-99` = Partially open

**Conversion Formula:**
```
HA position = 100 - Exalus position
Exalus position = 100 - HA position
```

Example:
- Set HA to 25% (mostly closed): Send `100 - 25 = 75` to Exalus
- Receive Exalus 75: Display as HA `100 - 75 = 25`

---

## Architecture

### File Structure
```
custom_components/exalushome_local/
├── api/
│   ├── __init__.py          # Module exports
│   ├── client.py            # WebSocket client implementation
│   └── models.py            # Data models (Device, Channel, ShutterDevice, etc.)
├── __init__.py              # Integration setup/teardown
├── config_flow.py           # Configuration UI flow
├── const.py                 # Protocol constants and position conversion
├── coordinator.py           # Data update coordinator
├── cover.py                 # CoverEntity implementation
├── manifest.json            # Integration metadata
└── NOTES.md                 # This file
```

### Data Flow

1. **User Configuration** → `config_flow.py` collects host, serial, PIN
2. **Initialization** → `__init__.py` stores config, platforms setup
3. **Coordinator Setup** → `coordinator.py` creates `ExalusLocalClient`
4. **WebSocket Connection** → `api/client.py` connects to `ws://{host}:81/`
5. **State Updates** → WebSocket receives state events, triggers coordinator refresh
6. **Cover Entities** → `cover.py` creates `CoverEntity` for each shutter
7. **Commands** → User actions in HA → `cover.py` → `coordinator.py` → `api/client.py` → WebSocket

### Coordinator Role

- Manages single WebSocket connection (reused for all shutters)
- Refreshes state on polling interval
- Listens for WebSocket state change events
- Caches shutter device list
- Routes commands to WebSocket client

### Cover Entity Mapping

Each `IDeviceChannel` with `ControlFeature.Blind` becomes one `CoverEntity`:
- **unique_id:** `exalushome_local_{device_guid}_{channel_number}`
- **name:** `{device_name} {channel_name}`
- **position:** Current blind position (HA scale: 0=closed, 100=open)
- **is_closed:** Position == 0
- **supported_features:** OPEN, CLOSE, STOP, SET_POSITION

---

## Validated Behaviors

### Open/Close/Stop
✅ `open` command sends code `101`  
✅ `close` command sends code `102`  
✅ `stop` command sends code `103`  
✅ All commands routed through single WebSocket

### Position Control
✅ Set position by sending numeric value (0-100 Exalus scale)  
✅ Position feedback received in state events  
✅ HA position automatically inverted for display

### Movement State
✅ `TaskExecution = 1` indicates movement in progress  
✅ `TaskExecution = 0` indicates movement stopped  
⚠️ **Limitation:** Cannot distinguish `is_opening` from `is_closing`  
  - Only flag available: "currently moving" (yes/no)
  - Workaround: Would require tracking previous position + time delta
  - Current implementation: Optimistic position update on command, state sync on event

### Availability
✅ Device state `Working = 1` means available  
✅ Unavailable device state: `NotResponding = 0`, `Broken = 2`, etc.  
✅ Cover `.available` reflects device availability
