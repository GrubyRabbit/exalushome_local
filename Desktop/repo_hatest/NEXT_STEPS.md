# Next Steps: HA Shutter Integration

## Current Status

**Analysis Complete:** ✅  
**Implementation Ready:** ⏳ (Blocked on position scale validation)  
**Deliverable:** NARROW_SCOPE_HA_SPEC.md (18KB, 587 lines)

## What's Confirmed

✅ **Remote Mode (Cloud)**
- Uses: ExalusConnectionService (Microsoft SignalR)
- Broker: exalushome.tr7.pl
- Auth: AuthorizationInfo(serialNumber, pin)

✅ **Local Mode (Direct IP)**
- Uses: LocalNetworkExalusConnectionService (WebSocket on port 81)
- Auth: Same as remote
- Discovery: Manual IP entry (controller validation via HTTP endpoint)

✅ **Shutter Control**
- Filtering: Roles 11 (Blind), 12 (Roller), 21 (BlindsWithPrecisePosition)
- Primary Command: SetBlindPosition(position: ???)
- State: IDeviceState with BlindPosition value
- Architecture: Device → Channels → States

✅ **Protocol**
- Universal: IDataFrame<T> for both modes
- Method: HTTP-like (Get=0, Post=1, Delete=2, Put=3)
- Status: OK=0, various errors 1-16
- Example: POST /devices/{id}/executeTask with {taskType, position}

## What's Unknown (Needs Validation)

### Critical (Blocks Implementation)

**1. Position Scale** ⚠️ BLOCKING
- Question: What are valid position values?
- Options: 0-100%, 0-255 (8-bit), 0-180 (degrees), or other?
- Impact: HIGH (affects open/close direction mapping in HA)
- Effort: 30 minutes (web app sniffing)

**2. Stop Command** ⚠️ BLOCKING  
- Question: How to stop blind mid-movement?
- Options: SetBlindPositionSimple payload? Special position value? Unknown command?
- Impact: MEDIUM (affects CoverEntity.STOP feature)
- Effort: 15 minutes (capture API call in web app)

### Important (Improves Quality)

**3. Movement Direction**
- Question: Can we distinguish is_opening vs is_closing?
- Impact: MEDIUM (affects HA state feedback)
- Effort: 15 minutes

**4. State Update Frequency**
- Question: How often does position update? Push or polling?
- Impact: LOW (can use reasonable default)
- Effort: 10 minutes

**Total Validation Time: 2-3 hours**

## Validation Instructions

### Quick Method: Web App Sniffing

1. **Prepare**
   - Open https://exalushome.tr7.pl/ in browser
   - Open DevTools (F12) → Network tab
   - Filter: XHR (XMLHttpRequest)
   - Login with ExalusHome account

2. **Test Position Scale**
   - Move blind to **fully open** (0%)
     - Capture API call: look at `/devices/{id}/executeTask` POST
     - Note the `position` value in request body
   - Move blind to **50%**
     - Capture position value
   - Move blind to **fully closed** (100%)
     - Capture position value
   
   **Determine scale:**
   - If values are 0, 50, 100 → **0-100% scale**
   - If values are 0, 127, 255 → **0-255 scale**
   - If values are 0, 90, 180 → **0-180° scale**

3. **Test Stop Command**
   - Start blind movement (any direction)
   - Click the Stop button in web app
   - Capture the API call that executes
   - Note task type and payload

4. **Document Results**
   - Update NARROW_SCOPE_HA_SPEC.md section "Unknowns"
   - Record exact API payloads observed

### Alternative Method: Hardware Testing
- If you have an ExalusHome controller on local network
- Connect via local mode (port 81)
- Run test scripts to verify position values empirically

## Implementation Plan

Once validation is complete:

### Phase 1: Python API Layer (2-3 hours)
```
exalushome_api/
├── base.py              # Abstract API class
├── remote.py            # SignalR implementation
└── local.py             # WebSocket implementation
```

### Phase 2: Home Assistant Integration (3-4 hours)
```
custom_components/exalushome/
├── __init__.py          # Setup integration
├── const.py             # Constants
├── config_flow.py       # Config UI (remote/local selection)
├── cover.py             # CoverEntity for shutters
├── manifest.json        # Integration metadata
└── strings.json         # Translations
```

### Phase 3: Testing & Refinement (2-3 hours)
- Unit tests for API layer
- Integration tests with HA
- Hardware testing if available

**Total Implementation Time: 7-10 hours** (after validation)

## Files in Repository

### Current
- `NARROW_SCOPE_HA_SPEC.md` — Complete specification (18KB)
- `research/` — Detailed analysis (from earlier phases)
- `scripts/` — Analysis tools (not needed for implementation)

### To Create
- `exalushome_api/base.py` — Abstract API (start here)
- `exalushome_api/remote.py` — SignalR wrapper
- `exalushome_api/local.py` — WebSocket wrapper
- `custom_components/exalushome/` — HA integration

## Recommended Sequence

1. **Validate unknowns** (2-3 hours) — See Validation Instructions above
2. **Update NARROW_SCOPE_HA_SPEC.md** with findings
3. **Implement exalushome_api/base.py** — Core abstraction
4. **Implement exalushome_api/remote.py** — Test with cloud account
5. **Implement exalushome_api/local.py** — Test with local controller (if available)
6. **Implement custom_components/exalushome/** — HA integration
7. **Test** and refine

## Quick Test: Check Position Scale

Before full validation, you can do a quick check:

```python
# If you have local controller access:
import asyncio
from websocket import create_connection

ws = create_connection("ws://192.168.1.100:81")
# Send authentication frame (serialize IDataFrame)
# Send GetState request
# Capture position value
# Repeat for different blind positions
```

## Questions?

See **NARROW_SCOPE_HA_SPEC.md** for detailed:
- Connection interfaces
- Protocol documentation
- Entity schema
- Command structures
- Architecture recommendations

## Repository

All code is tracked in:  
**https://github.com/GrubyRabbit/hatest.git**

Commits:
- `ee89d18` — Full research (2,930+ lines)
- `f8af4f6` — Narrow-scope HA spec (this deliverable)
