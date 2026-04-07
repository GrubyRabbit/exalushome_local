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

---

## Known Limitations & TODOs

### Critical TODOs (blocking features)

1. **Device Discovery** (`client.py:167`)
   - Local API device fetch not documented in npm
   - Current: `fetch_devices()` returns empty
   - TODO: Implement discovery via:
     - HTTP GET `/system/devices`? (unknown endpoint)
     - Or require manual device configuration
     - Or parse from web app if available
   - **Impact:** Integration won't show any shutters until implemented

2. **State Update Parsing** (`coordinator.py:75`, `client.py:145`)
   - WebSocket state event structure not fully mapped
   - Current: Events received but not parsed into device state
   - TODO: Parse JSON structure into `Device` and `ShutterDevice` objects
   - **Impact:** Position and movement state won't update after connection

3. **Position Feedback** (`cover.py:165-170`)
   - Cannot distinguish `is_opening` vs `is_closing`
   - Only `TaskExecution` flag (0/1) available
   - TODO: Implement optional state tracking:
     - Option A: Track `(previous_position, current_time)`, infer direction
     - Option B: Add TODO markers and accept limitation
   - **Current:** Shows as `is_opening` when moving (imperfect)

### Minor TODOs (nice-to-have)

4. **HTTP Keep-alive** (`client.py:1`)
   - Research indicates `/system/ping` HTTP endpoint (not in WebSocket)
   - Current: Not implemented
   - TODO: Optional HTTP polling for connection health

5. **Error Recovery**
   - WebSocket disconnection not handled gracefully
   - TODO: Auto-reconnect logic with backoff
   - TODO: Queued command retry mechanism

6. **Logging Redaction**
   - Credentials may appear in debug logs
   - TODO: Add redaction for `serial` and `pin` values

---

## Assumptions

### WebSocket Message Format
Based on npm research (not runtime-validated):

**Assumption 1:** JSON-based messages with `type` field
```json
{
  "type": "DataFrameCommand" | "DeviceStateChanged" | "AuthorizationInfo",
  "data": {...}
}
```

**Assumption 2:** State events include:
- Device GUID
- Channel number
- Position (Exalus scale 0-100)
- TaskExecution state (0=stopped, 1=moving)

**Why:** npm classes document these fields; local validation confirms position scale and command codes only.

### Device GUID Uniqueness
- Assumption: `device_guid + channel_number` is globally unique per controller
- Used for `entity_id` generation
- **Risk:** If same GUID used in multiple controllers, entity_id collision
- **Mitigation:** Include controller serial in unique_id if needed (Phase 2)

### Port 81 Hardcoding
- Assumption: All controllers use port 81
- npm source confirms hardcoded `_port = "81"`
- **Risk:** Newer firmware versions might change port
- **Mitigation:** Make port configurable in Phase 2 if needed

---

## Testing Checklist (Before Real Hardware)

- [ ] Config flow accepts host, serial, pin
- [ ] Connection attempt succeeds/fails gracefully
- [ ] No exceptions on disconnect
- [ ] Coordinator startup completes without errors
- [ ] CoverEntity attributes initialize correctly

## Testing Checklist (On Real Hardware)

- [ ] Open/close/stop commands transmit successfully
- [ ] Position update events received after command
- [ ] Position correctly inverted (HA 0=closed, Exalus 0=open)
- [ ] Multiple blinds work independently
- [ ] Disconnect/reconnect cycle works
- [ ] Error recovery (power cycle) works
- [ ] No deadlocks or infinite loops

---

## Next Implementation Phases

### Phase 1: Device Discovery (Critical)
- Implement local device fetch via HTTP or WebSocket
- Parse device/channel structure
- Populate coordinator data

### Phase 2: State Synchronization (Critical)
- Parse WebSocket state events
- Update coordinator on position/moving changes
- Trigger cover entity state refresh

### Phase 3: Error Handling (Important)
- Auto-reconnect on disconnect
- Command retry with backoff
- Graceful degradation if connection fails

### Phase 4: Feature Expansion (Optional)
- Remote mode support (SignalR via cloud)
- Device configuration UI
- Diagnostics and logs redaction
- Performance optimization (batched commands)

---

## References

- **VALIDATION_PLAYBOOK_HA.md** — Validated protocol findings
- **EVIDENCE_MATRIX_HA.md** — Claim sources and confidence levels
- **NARROW_SCOPE_HA_SPEC.md** — Architecture and requirements
- **research/auth_local.md** — Local connection details
- **research/commands.md** — Command structure
- **research/entities.md** — Device/channel models
