# ExalusHome Local Integration - Quick Reference

## Getting Started

### Files You Need to Know

**Most Important:**
- `custom_components/exalushome_local/cover.py` — CoverEntity (what HA users interact with)
- `custom_components/exalushome_local/api/client.py` — WebSocket communication
- `custom_components/exalushome_local/const.py` — Protocol constants

**For Understanding:**
- `IMPLEMENTATION_STATUS.md` — Progress and next steps
- `custom_components/exalushome_local/NOTES.md` — Implementation details
- `VALIDATION_PLAYBOOK_HA.md` — How the protocol was validated

### Key Implementation Details

**Position Mapping (Critical)**
```python
from custom_components.exalushome_local.const import exalus_to_ha_position, ha_to_exalus_position

# When receiving position from Exalus (0=open, 100=closed):
ha_position = exalus_to_ha_position(exalus_position)  # Inverts to HA scale (0=closed, 100=open)

# When sending position to Exalus:
exalus_position = ha_to_exalus_position(ha_position)  # Inverts from HA scale
```

**Control Commands**
```python
from custom_components.exalushome_local.const import (
    BLIND_CONTROL_OPEN,      # 101
    BLIND_CONTROL_CLOSE,     # 102
    BLIND_CONTROL_STOP,      # 103
)

# Send open: coordinator.send_command(device_guid, channel_number, BLIND_CONTROL_OPEN)
# Send close: coordinator.send_command(device_guid, channel_number, BLIND_CONTROL_CLOSE)
# Send stop: coordinator.send_command(device_guid, channel_number, BLIND_CONTROL_STOP)
# Set position: coordinator.send_command(device_guid, channel_number, exalus_position_value)
```

**Entity Unique ID**
```python
unique_id = f"exalushome_local_{device_guid}_{channel_number}"
```

---

## Current State (Phase 1)

### ✅ What Works

- Config flow accepts host/serial/pin
- WebSocket client connects and sends commands
- CoverEntity attributes initialized
- Position conversion implemented
- Data models defined
- Coordinator structure ready

### ❌ What's Missing (Phase 2)

1. **Device discovery** — Need to fetch devices from controller
2. **State parsing** — WebSocket events received but not parsed
3. **Movement direction** — Cannot tell open vs close (limitation)

---

## Testing Locally

### Prerequisites

- Home Assistant dev environment or test instance
- Python 3.9+
- `websockets` library (add to requirements if needed)

### Quick Test

```python
# Test WebSocket client directly
from custom_components.exalushome_local.api.client import ExalusLocalClient

client = ExalusLocalClient(
    host="192.168.1.100",
    serial="ABC123",
    pin="0000"
)

# Connect
if await client.connect():
    print("Connected!")
    
    # Send open command
    await client.send_command(
        device_guid="some-guid",
        channel_number=0,
        command=101  # Open
    )
    
    await client.disconnect()
```

---

## TODOs for Phase 2

### Priority 1 (Blocking)

**Device Discovery** — `api/client.py:167`
- Implement `fetch_devices()` method
- Need local API endpoint (unknown — research needed)
- Return list of Device objects

**State Parsing** — `coordinator.py:75`, `api/client.py:145`
- Parse WebSocket events into device state
- Update position, moving flag, availability
- Trigger coordinator refresh

**Direction Detection** — `cover.py:165-170`
- Track position history to infer direction
- Set `is_opening` / `is_closing` correctly

### Priority 2 (Important)

**Error Recovery** — `coordinator.py`
- Auto-reconnect on disconnect
- Command queue/retry
- Graceful degradation

**Keep-Alive** — `client.py`
- Optional HTTP ping to `/system/ping`
- Maintain connection liveness

### Priority 3 (Nice-to-Have)

**Remote Mode** — New coordinator
- Cloud connection via SignalR
- Mode selector in config_flow

**Diagnostics** — Add redaction/logging
- Redact credentials in logs
- Export device tree

---

## Integration Flow

```
HA User
  ↓ (adds integration in settings)
  ↓
ConfigFlow
  ↓ (validates host/serial/pin)
  ↓
__init__.py (async_setup_entry)
  ↓ (creates coordinator)
  ↓
Coordinator
  ↓ (creates WebSocket client)
  ↓
ExalusLocalClient (connect)
  ↓ (ws://{host}:81/)
  ↓
Blind Controller
```

```
Controller State Change
  ↓ (WebSocket event)
  ↓
ExalusLocalClient (_on_state_changed)
  ↓ (callback)
  ↓
Coordinator (notify)
  ↓
CoverEntity (state_changed)
  ↓
HA Updates Position / Availability
```

---

## Common Issues

**Q: Why does position seem inverted?**  
A: ExalusHome uses 0=open, 100=closed. HA uses 0=closed, 100=open. The `exalus_to_ha_position()` function handles this.

**Q: Why don't I see any blinds?**  
A: Device discovery not implemented yet. Phase 2 task.

**Q: Why doesn't the position update?**  
A: State parsing not implemented yet. Phase 2 task.

**Q: Why can't I tell if the blind is opening vs closing?**  
A: Only `TaskExecution` flag available (moving=yes/no). Would need to track history. Phase 2 task.

---

## Resources

- **Validated protocol:** `VALIDATION_PLAYBOOK_HA.md`
- **Code sources:** `EVIDENCE_MATRIX_HA.md`
- **Requirements:** `NARROW_SCOPE_HA_SPEC.md`
- **Detailed notes:** `custom_components/exalushome_local/NOTES.md`
- **Implementation notes:** This file + code comments

---

## Next Command

```bash
# Continue to Phase 2
# Review IMPLEMENTATION_STATUS.md
# Pick one of 3 critical items to implement first
# Recommendation: Start with Device Discovery (highest impact)
```
