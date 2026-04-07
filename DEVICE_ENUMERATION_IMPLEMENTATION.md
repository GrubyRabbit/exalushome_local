# Device Enumeration - Implementation Evidence

## Problem
Device enumeration endpoint for local ExalusHome controller was not documented in npm packages, requiring inference from protocol patterns.

## Evidence-Based Solution

### 1. Discovery Method from npm
**Source:** `research/auth_findings.json`
```
"GetDevicesAsync(withScenes?: boolean): Promise<IDevice[]>"
```
- **Exists on:** IExalusConnectionService (both remote and local implementations)
- **Returns:** Array of IDevice objects
- **Interpretation:** Method exists but implementation details not documented

### 2. Device & Channel Structure
**Source:** `research/entities.md` (lines 6-58)

```typescript
interface IDevice {
  Guid: string;                    // Unique device ID
  Name: string;                    // User-defined name
  State: DeviceState;              // Working (1), NotResponding (0), Broken (2)
  Channels: IDeviceChannel[];      // Control channels
}

interface IDeviceChannel {
  Number: number;                  // Channel index
  Name: string;                    // Channel name
  ControlFeature: number;          // 3 = Blind/Shutter
  IsAvailable: boolean;            // Channel availability
}
```

### 3. Protocol Pattern Analysis
**Source:** `research/auth_local.md` (lines 278-287)

Known endpoints:
- `/system/authorize` — Authentication (METHOD_POST)
- `/system/ping` — Keep-alive (METHOD_GET)
- `/devices/device/control` — Commands (METHOD_POST)
- `/info/devices/device/state/changed` — State events (WebSocket subscription)

**Inferred pattern:**
- `/system/*` = System-level operations
- `/info/*` = Information/status resources
- Therefore: `/info/devices` (GET) = Device list endpoint

### 4. Response-to-Request Matching
**Evidence Source:** IDataFrame protocol structure

All requests and responses use:
```json
{
  "TransactionId": "<uuid>",
  "Resource": "/<endpoint>",
  "Method": <0|1|2|3>,
  "Data": {...},
  "Status": <0|...>
}
```

**Implementation:** TransactionId is matched to correlate responses with requests

---

## Implementation Changes

### api/client.py Changes

#### 1. Added Response Tracking (Line 54)
```python
self._pending_responses: Dict[str, asyncio.Future] = {}  # TransactionId -> Future
```
- Stores futures for pending requests
- Allows matching responses to requests

#### 2. Updated Message Handler (Lines 164-200)
```python
# Check if this is a response to a pending request
transaction_id = data.get("TransactionId")
if transaction_id and transaction_id in self._pending_responses:
    future = self._pending_responses.pop(transaction_id)
    if not future.done():
        future.set_result(data)
    return
```
- Routes responses to pending requests
- Resolves futures so fetch_devices() can receive responses

#### 3. Implemented fetch_devices() (Lines 279-335)
```python
async def fetch_devices(self) -> Dict[str, Device]:
    # 1. Create TransactionId and Future for response
    # 2. Send IDataFrame to /info/devices with METHOD_GET
    # 3. Wait for response (timeout 5 seconds)
    # 4. Parse response via _parse_device_list_response()
    # 5. Return Dict[device_guid -> Device]
```

**Key behaviors:**
- Checks connection and authorization before requesting
- Implements timeout (5 seconds) to fail gracefully
- Logs success/failure

#### 4. Implemented _parse_device_list_response() (Lines 337-424)
```python
def _parse_device_list_response(self, response: Dict[str, Any]) -> Dict[str, Device]:
    # 1. Extract Data array from response
    # 2. For each device_obj in Data:
    #    a. Parse Guid, Name, State
    #    b. For each channel in Channels:
    #       - Parse Number, Name, ControlFeature
    #       - Create DeviceChannel object
    #    c. Create Device object
    # 3. Return Dict indexed by device GUID
```

**Response structure assumed:**
```json
{
  "Status": 0,
  "Data": [
    {
      "Guid": "<device-guid>",
      "Name": "Device Name",
      "State": 1,
      "SerialNumber": "...",
      "Channels": [
        {
          "Number": 0,
          "Name": "Channel 0",
          "ControlFeature": 3
        }
      ]
    }
  ]
}
```

### models.py - No Changes
Existing Device and DeviceChannel dataclasses already match required structure.

### coordinator.py - No Changes
Existing `_extract_shutters()` and `_async_update_data()` already properly use `fetch_devices()` output.

---

## Evidence-Backed Assumptions

### Endpoint Path: `/info/devices`
**Reasoning:**
1. Pattern: `/info/devices/device/state/changed` exists (confirmed)
2. `/info` is for information/status resources
3. Parent path `/info/devices` likely contains device list
4. **Alternative if wrong:** `/system/devices` (system-level operation)

### Response Structure
**Reasoning:**
1. IDevice interface has Guid, Name, State, Channels fields (confirmed from research)
2. IDeviceChannel has Number, Name, ControlFeature fields (confirmed from research)
3. JSON response likely mirrors TypeScript interface structure
4. Data field in IDataFrame contains payload

### Filtering Blind/Shutter Devices
**Reasoning:**
1. ControlFeature=3 means Blind (confirmed from research)
2. Channel.is_blind() checks: `control_feature == ControlFeature.Blind`
3. Coordinator filters via device.get_blind_channels()

---

## Remaining Unknowns (Blocking Web App Validation)

1. **Exact endpoint path**
   - Tested: `/info/devices` (likely)
   - Fallback: `/system/devices`
   - Unknown: Could be `/devices` or `/info/devicesList` or other

2. **Exact response structure**
   - Tested: Response.Data is array of devices
   - Unknown: Field names exact case, nested structure, optional fields

3. **Channel filtering**
   - Assumption: ControlFeature=3 for blinds
   - Unknown: Are there other device types in response? What are their ControlFeature values?

4. **Device state availability**
   - Assumption: State enum Working=1, NotResponding=0, Broken=2
   - Unknown: Are these exact values?

---

## Testing Steps (Web App Capture Required)

1. **Open Chrome DevTools** → Network tab
2. **Filter by:**
   - URL containing "device"
   - Type "ws" or "wss" (WebSocket)
3. **Trigger device enumeration:**
   - Reload the web app
   - Open Devices/Rooms view
   - Look for first WebSocket message sent after auth
4. **Capture the frame:**
   - Note the Resource field
   - Note the response Status and Data structure
   - Record exact field names

5. **Execute test:**
   - If Status=0 (success): compare our parsing
   - If Status!=0 (error): may indicate wrong endpoint
   - If timeout: endpoint path likely wrong

---

## Files Modified
- `custom_components/exalushome_local/api/client.py` — Added device enumeration
  - Lines 54: Added _pending_responses dict
  - Lines 164-200: Updated _handle_message() for response matching
  - Lines 279-335: Implemented fetch_devices()
  - Lines 337-424: Implemented _parse_device_list_response()

## Files Not Modified (Already Correct)
- `api/models.py` — Device/DeviceChannel structures match
- `coordinator.py` — Properly uses fetch_devices() output
- `cover.py` — Entity implementation still valid

---

## Next Steps

1. **Validate endpoint via web app** → Compare actual frames
2. **If validation passes:**
   - Test against real ExalusHome controller
   - Verify devices and channels appear in HA
3. **If validation fails:**
   - Adjust endpoint path (try `/system/devices`, `/devices`, etc.)
   - Adjust response parsing if field names differ
   - Capture actual request/response from web app
