# Validation Playbook: ExalusHome Blocking Unknowns

**Goal:** Determine position scale, stop command mechanism, and open/close direction mapping using official web app + Chrome DevTools.

**Duration:** 1-2 hours of active testing

**Blinds Required:** At least one working blind with open/close/stop controls

---

## PART 1: CHROME DEVTOOLS SETUP

### Step 1.1: Open Web App and DevTools
```
1. Open https://exalushome.tr7.pl/ in Chrome
2. Log in with test credentials
3. Press F12 to open DevTools
4. Click "Network" tab
5. Ensure "Preserve log" is checked (⚙️ → Preserve log)
6. Set filter dropdown: "XHR/Fetch" (to show only API calls, not page resources)
```

### Step 1.2: Identify Device and Channel IDs
```
Action: Find the blind/shutter device and note its IDs

In web app:
1. Navigate to the blind control section
2. Locate the blind you'll test (must support open/close/stop)
3. Right-click on the blind name → Inspect Element (or use DevTools Search)
4. Look for data attributes: 
   - data-device-id
   - data-device-guid
   - data-channel-id
   - data-device-uuid
5. Record these IDs - you'll use them to filter network requests

Alternative method (URL-based):
1. Move any blind to halfway position
2. Open Network tab
3. Look for POST request to `/devices/` endpoint
4. Note the {device-guid} in Resource column
5. Record this GUID for filtering

Expected IDs format:
   - Device GUID: "a1b2c3d4-e5f6-g7h8-i9j0-k1l2m3n4o5p6"
   - Channel ID: "0", "1", "2" (numeric)
```

### Step 1.3: Set Up Network Filter
```
Chrome DevTools Network tab:

1. Click filter icon (funnel icon)
2. Type: -websocket -json
   (This filters out WebSocket noise, shows HTTP requests)
3. Alternative filter for SignalR: 
   Type: "negotiate OR signalr"
   (To see SignalR handshake and hubs)

OR filter for specific endpoints:
   Type: "/devices/"
   (Shows only device-related API calls)
```

---

## PART 2: CAPTURE BASELINE STATE

### Step 2.1: Record Initial Blind State
```
Before moving anything:

1. Stop all DevTools recording (clear Network tab)
2. Verify blind is at known position (fully open or fully closed)
3. In Network tab, right-click on any request → Copy as cURL
4. Look for: GET /devices/{device-guid}/state
   (If not visible, manually trigger refresh in web app)
5. Record the response JSON:

   Expected response structure:
   {
     "deviceGuid": "{guid}",
     "states": [
       {
         "type": "IBlindPosition",
         "data": <NUMBER>  ← RECORD THIS VALUE
       },
       {
         "type": "IBlindOpenCloseTime",
         "data": {...}
       },
       {
         "type": "TaskExecution",
         "data": <0 or 1>  ← 0=stopped, 1=moving
       }
     ]
   }

6. Record:
   - Current position value
   - Whether blind is moving (TaskExecution)
   - Timestamp (for filtering later events)
```

### Step 2.2: Distinguish State Events from Command Events
```
Problem: Network tab will show many requests. How to distinguish:
- State refresh requests (GET, automatic polling)
- Command requests (POST, user-initiated)
- State change responses (from command side effects)

Solution: Filter by request TYPE and RESOURCE

State refresh (automatic):
  ✓ Method: GET
  ✓ Resource: /devices/{guid}/state
  ✓ No "Data" field in request body
  ✓ Happens periodically (every 5-30s)

Command request (user-initiated):
  ✓ Method: POST
  ✓ Resource: /devices/{guid}/executeTask
  ✓ Has "Data" field with task definition
  ✓ Example: { "taskType": "IBlindPosition", "position": 50 }
  ✓ Timestamp matches when you clicked button

State change response (effect of command):
  ✓ Method: GET (follows POST command within 1-2s)
  ✓ Resource: /devices/{guid}/state
  ✓ Response "data" field differs from baseline
```

---

## PART 3: TEST POSITION VALUES

**Test Matrix:**
Test these exact positions in this order (to cover full range):
- 0 (test if it means fully open or fully closed)
- 1 (test sensitivity at minimum)
- 25 (quarter)
- 50 (half, reference point)
- 75 (three-quarter)
- 99 (test sensitivity at maximum)
- 100 (test if it means fully closed or fully open)

### Step 3.1: Test Position = 0

```
Pre-test:
1. Clear Network tab (trash icon)
2. Record timestamp: ___________

Action:
1. Locate blind control with position slider (0-100%)
2. Set position to 0%
3. Click "Set" or button that sends command

Network capture:
1. Look for POST request to /devices/{device-guid}/executeTask
2. Click on request → "Request" tab
3. Copy the JSON body:

   Expected structure:
   {
     "Resource": "/devices/{device-guid}/executeTask",
     "Method": 1,
     "TransactionId": "req_XXXX",
     "Data": {
       "taskType": "IBlindPosition",
       "position": <ACTUAL_VALUE_SENT>  ← RECORD
     }
   }

4. Record in result template:
   - Actual value sent to API: ___________
   - Expected by user: 0% (fully open or fully closed?)

Response capture:
1. Click on same POST request → "Response" tab
2. Status should be 0 (OK)
3. Record the response structure:

   {
     "Resource": "/devices/{guid}/executeTask",
     "Status": 0,
     "Data": {
       "executionId": "...",
       "result": "Success"
     }
   }

State verification (1-2 seconds after command):
1. Look for subsequent GET /devices/{guid}/state request
2. Click on it → "Response" tab
3. Find IBlindPosition value:

   "type": "IBlindPosition",
   "data": <ACTUAL_POSITION_AFTER_COMMAND>  ← RECORD

Record this value (should match what you sent)
```

### Step 3.2: Repeat for Positions: 1, 25, 50, 75, 99, 100

```
For EACH position value:

1. Clear Network tab
2. Note timestamp
3. Set web app position slider to exact value
4. Click send/set button
5. Capture in Network tab:
   - POST Data field value (what was sent)
   - Response Status (should be 0)
   - Subsequent GET /devices/{guid}/state response IBlindPosition value
6. Fill in result template row:

   | Test # | Set To | API Sent | State After | Notes |
   |--------|--------|---------|------------|-------|
   | 1      | 0%     | ?       | ?          | Is this fully open? |
   | 2      | 1%     | ?       | ?          |       |
   | 3      | 25%    | ?       | ?          | Quarter position |
   | 4      | 50%    | ?       | ?          | Midpoint reference |
   | 5      | 75%    | ?       | ?          | Three-quarter |
   | 6      | 99%    | ?       | ?          |       |
   | 7      | 100%   | ?       | ?          | Is this fully closed? |
```

### Step 3.3: Analyze Position Scale

```
After testing all 7 positions, determine scale:

Pattern 1: Linear 0-100%
  Observed: Position sent = Position received
  Example: Send 0, receive 0; send 50, receive 50; send 100, receive 100
  Conclusion: ✓ Scale is 0-100% (percentage)

Pattern 2: Binary scaled 0-255
  Observed: Position received = (sent * 255) / 100
  Example: Send 0, receive 0; send 50, receive 127; send 100, receive 255
  Conclusion: ✓ Scale is 0-255 (8-bit)

Pattern 3: Angular 0-180
  Observed: Position received = (sent * 180) / 100
  Example: Send 0, receive 0; send 50, receive 90; send 100, receive 180
  Conclusion: ✓ Scale is 0-180 (degrees)

Pattern 4: Device-specific
  Observed: Values don't match any standard pattern
  Example: Complex mapping or non-linear scaling
  Conclusion: ⚠️ Device-specific, note exact mapping

FILL IN RESULT: Position scale is _________________ (0-100% / 0-255 / 0-180° / other)
```

---

## PART 4: TEST OPEN VS CLOSE DIRECTION

### Step 4.1: Move Blind Fully Open

```
Action:
1. Click "Open" button or set position to maximum opening
2. Wait for blind to physically move to fully open position

Network capture (same as Step 3.1):
1. Look for POST /devices/{guid}/executeTask
2. Record:
   - Position value SENT: ___________
   - Verify Status = 0 (OK)
3. Wait 1-2s for state update
4. Look for GET /devices/{guid}/state
5. Record IBlindPosition value received: ___________

Physical verification:
1. Look at blind - is it fully open? Yes / No
2. Take note of response position value

RECORD IN TEMPLATE:
   Fully open blind:
   - Position value: ___________
   - Is this 0 or 100?
   - Physical state: Open / Closed
```

### Step 4.2: Move Blind Fully Closed

```
Action:
1. Click "Close" button or set position to minimum opening
2. Wait for blind to physically move to fully closed position

Network capture (same as above):
1. Look for POST /devices/{guid}/executeTask
2. Record:
   - Position value SENT: ___________
   - Verify Status = 0 (OK)
3. Wait 1-2s for state update
4. Look for GET /devices/{guid}/state
5. Record IBlindPosition value received: ___________

Physical verification:
1. Look at blind - is it fully closed? Yes / No
2. Take note of response position value

RECORD IN TEMPLATE:
   Fully closed blind:
   - Position value: ___________
   - Is this 0 or 100?
   - Physical state: Closed / Open
```

### Step 4.3: Determine Direction Mapping

```
After Step 4.1 and 4.2, complete this logic:

If fully open position value = 0:
   ✓ Direction mapping: 0 = Open, 100 = Closed (standard HA)
   ✓ HA CoverEntity properties:
     - current_cover_position = received_position
     - is_closed = (position >= 80)  [threshold]
     - is_open = (position <= 20)    [threshold]

If fully open position value = 100:
   ⚠️ Direction mapping: 100 = Open, 0 = Closed (inverted)
   ⚠️ HA CoverEntity must invert logic:
     - current_cover_position = 100 - received_position
     - is_closed = (position <= 20)
     - is_open = (position >= 80)

FILL IN RESULT: Direction is _________________ (0=open or 100=open?)
```

---

## PART 5: TEST STOP COMMAND

### Step 5.1: Start Blind Movement

```
Action:
1. Clear Network tab
2. Click "Open" or "Close" button
3. DO NOT WAIT for movement to complete

Wait for feedback:
1. In Network tab, look for POST /devices/{guid}/executeTask
2. Verify Status = 0 (command accepted)

Verify movement started:
1. Look for TaskExecution state change
2. Search Network tab for GET /devices/{guid}/state
3. Find "type": "TaskExecution" in response
4. Value should be 1 (ExecutingTasks = 1, means moving)
5. Record timestamp: ___________
```

### Step 5.2: Click Stop Button Mid-Movement

```
Timing: Blind must be actively moving (TaskExecution = 1)

Action:
1. Click "Stop" button in web app
2. Immediately note exact timestamp: ___________

Network capture:
1. Look for NEW POST request after you clicked Stop
2. Find request to /devices/{guid}/executeTask
3. Click on request → "Request" tab → look at JSON body

Expected Stop command structure (TEST EACH):
Option A: SetBlindPositionSimple with special value
   {
     "Resource": "/devices/{guid}/executeTask",
     "Data": {
       "taskType": "SetBlindPositionSimple",
       "position": <SOME_VALUE>  ← RECORD
     }
   }

Option B: SetBlindPositionSimple with special enum
   {
     "Resource": "/devices/{guid}/executeTask",
     "Data": {
       "taskType": "SetBlindPositionSimple",
       "command": "Stop"  ← OR something like this
     }
   }

Option C: Current position as hold
   {
     "Resource": "/devices/{guid}/executeTask",
     "Data": {
       "taskType": "SetBlindPosition",
       "position": <CURRENT_POSITION_AT_TIME_OF_STOP>
     }
   }

Option D: Unknown mechanism
   Record whatever you see

RECORD IN TEMPLATE:
   - Stop command taskType: ___________
   - Stop command Data payload: ___________
   - Status in response: ___________
```

### Step 5.3: Verify Stop Executed

```
Verification:
1. Look for GET /devices/{guid}/state request (within 1-2s of Stop)
2. Check TaskExecution value:
   - If 0: Stop worked (ExecutingTasks = 0, no longer moving)
   - If 1: Unclear (still moving, or stop didn't work)
3. Check physical blind position:
   - Did it stop? Yes / No
   - Is it at halfway position? Yes / No

FILL IN RESULT:
   Stop command mechanism: ___________
   Confirmed working: Yes / No
   Evidence: ___________
```

---

## PART 6: COMPARE REMOTE VS LOCAL (Optional)

**If you have local controller access:**

### Step 6.1: Connect to Local Mode

```
Using second browser tab or separate session:

1. Configure HA or test app to connect to local controller (port 81)
2. Open same Chrome DevTools Network tab
3. Set filter: "websocket OR -websocket"
   (Shows both HTTP and WebSocket traffic)
```

### Step 6.2: Repeat Position Tests (Positions: 0, 50, 100)

```
Same test sequence as Part 3, but observe:
- Network patterns: Are they identical to remote?
- Request format: Same IDataFrame?
- Response structure: Same JSON format?
- Timing: Faster/slower than remote?

Expected: Behavior identical, only transport differs (WebSocket instead of HTTP)

For WebSocket inspection:
1. Click on WebSocket connection in Network tab
2. Go to "Messages" tab
3. Filter for frames containing "/devices" or your device GUID
4. Record the frame content (should be serialized IDataFrame)
```

---

## PART 7: VERIFY MOVEMENT STATE TRACKING

### Step 7.1: Track TaskExecution Flag

```
During open/close/stop sequence:

1. Move blind open
2. Immediately start monitoring GET /devices/{guid}/state responses
3. Record TaskExecution values over time:

   Time (s) | Action        | TaskExecution | Position |
   ---------|---------------|---------------|----------|
   0        | Click Open    | 0 (before)    | 50       |
   0.5      | Moving        | 1             | 51       |
   1.0      | Moving        | 1             | 53       |
   2.0      | Moving        | 1             | 55       |
   3.0      | Click Stop    | 1 (still)     | 57       |
   3.5      | Stopped       | 0             | 57       |

4. Conclusion: Can we distinguish direction?
   - No: Only 0=stopped, 1=moving (cannot tell if opening vs closing)
   - Yes: If state has directional information (record it)
```

---

## PART 8: FINAL EVIDENCE CHECKLIST

Before finalizing, verify you captured all required data:

```
POSITION SCALE VALIDATION:
  ☐ Tested position = 0, recorded API value sent and received
  ☐ Tested position = 50, recorded API value sent and received
  ☐ Tested position = 100, recorded API value sent and received
  ☐ Tested at least 3 additional positions (1, 25, 75, 99)
  ☐ All API responses showed Status = 0 (OK)
  ☐ Position values sent matched your web app input
  ☐ Determined scale: 0-100% / 0-255 / 0-180° / other

DIRECTION MAPPING VALIDATION:
  ☐ Moved blind fully open, recorded position value
  ☐ Moved blind fully closed, recorded position value
  ☐ Confirmed physical blind state (open or closed)
  ☐ Determined which position = open, which = closed
  ☐ Recorded exact position values for fully open and fully closed

STOP COMMAND VALIDATION:
  ☐ Started blind movement (Open or Close)
  ☐ Verified TaskExecution = 1 (moving) in state
  ☐ Clicked Stop button mid-movement
  ☐ Captured POST /devices/{guid}/executeTask request for Stop
  ☐ Recorded Stop command taskType and payload structure
  ☐ Verified TaskExecution = 0 after Stop (stopped)
  ☐ Verified physical blind stopped moving

NETWORK REQUEST VALIDATION:
  ☐ All requests used /devices/{device-guid}/executeTask endpoint
  ☐ All requests had Status = 0 in response (OK)
  ☐ All responses matched IDataFrame protocol structure
  ☐ State changes visible in subsequent GET /devices/{guid}/state
  ☐ Captured both command requests (POST) and state responses (GET)

DEVICE/CHANNEL IDENTIFICATION:
  ☐ Recorded device GUID: ___________
  ☐ Recorded channel ID: ___________
  ☐ Confirmed blind is shutter type (Roles: 11, 12, 21, or 23)
  ☐ Confirmed blind supports: open, close, stop, set position
```

---

## PART 9: RESULT TEMPLATE

**Fill this out manually after testing. Copy and save to new GitHub issue or VALIDATION_RESULTS.md**

```markdown
# Validation Results: ExalusHome Position Scale, Direction, Stop

Date Tested: ___________
Tester: ___________
Device: ___________
Environment: Production web app https://exalushome.tr7.pl/

## 1. POSITION SCALE DETERMINATION

### Tested Positions

| Position (%) | API Sent | API Received | Notes |
|--------------|----------|-------------|-------|
| 0            | ___      | ___         | |
| 1            | ___      | ___         | |
| 25           | ___      | ___         | Quarter |
| 50           | ___      | ___         | Midpoint |
| 75           | ___      | ___         | Three-quarter |
| 99           | ___      | ___         | |
| 100          | ___      | ___         | |

### Scale Determination

**Scale is:** ☐ 0-100% / ☐ 0-255 / ☐ 0-180° / ☐ Other: ___________

Evidence: ___________

---

## 2. OPEN VS CLOSE DIRECTION

### Fully Open State

Position value when blind is fully open: ___________
Is this 0 or 100? ___________
Physical blind state verified: ✓ Open / ☐ Closed

API request when setting to open:
```
{
  "taskType": "IBlindPosition",
  "position": ___________
}
```

### Fully Closed State

Position value when blind is fully closed: ___________
Is this 0 or 100? ___________
Physical blind state verified: ☐ Open / ✓ Closed

API request when setting to closed:
```
{
  "taskType": "IBlindPosition",
  "position": ___________
}
```

### Direction Mapping Conclusion

**Mapping is:** ☐ 0=Open, 100=Closed / ☐ 100=Open, 0=Closed / ☐ Other: ___________

For HA implementation:
- is_open when position <= ___________
- is_closed when position >= ___________

---

## 3. STOP COMMAND MECHANISM

### Stop Command Structure

When Stop button clicked during movement:

Request taskType: ___________
Request Data payload:
```
{
  "taskType": "___________",
  "___________": ___________
}
```

Response Status: ___________
Did blind stop? ✓ Yes / ☐ No

### Alternative Stop Methods

If SetBlindPositionSimple does NOT work, test:
☐ Sending current position as SetBlindPosition
☐ Special enum value
☐ Unknown mechanism

Result: ___________

---

## 4. MOVEMENT STATE TRACKING

Can distinguish is_opening vs is_closing? ☐ Yes / ☐ No

If yes, how: ___________

If no, fallback: Use is_moving = (TaskExecution == 1)

---

## 5. STATE UPDATE FREQUENCY

Observed update pattern: ☐ Polling / ☐ Push / ☐ Hybrid

Polling interval (if applicable): ___________ seconds

Evidence: ___________

---

## 6. REMOTE VS LOCAL COMPARISON

Tested local mode: ☐ Yes / ☐ No

If yes:
- Same behavior as remote? ✓ Yes / ☐ No
- Key differences: ___________

---

## 7. UNKNOWNS SUMMARY

| Unknown | Status | Value | Confidence |
|---------|--------|-------|------------|
| Position scale | ✓ Resolved | ___ | Confirmed |
| Stop command | ✓ Resolved | ___ | Confirmed |
| Open/close direction | ✓ Resolved | ___ | Confirmed |
| Movement direction | ☐ Unresolved | N/A | TBD |
| Update frequency | ☐ Unresolved | N/A | TBD |

---

## 8. READY FOR IMPLEMENTATION

All blocking unknowns resolved: ✓ Yes / ☐ No

If yes, proceed to IMPLEMENTATION_PLAN_HA.md Phase 1: Data Models

If no, unknowns still pending: ___________
```

---

## PART 10: TROUBLESHOOTING

### Problem: Cannot find POST request for command

```
Solution 1: Check Network filter
  - Remove filters temporarily
  - Look for any request with timestamp matching when you clicked button
  - Device GUID should be in URL

Solution 2: Check request body encoding
  - Request might be compressed (gzip)
  - Right-click request → "Copy as cURL"
  - Paste in text editor to see actual body

Solution 3: Command might use SignalR instead of HTTP
  - Look for "negotiate" or "signalr" in Network tab
  - Switch to WebSocket inspection (see Part 6)
```

### Problem: Position values don't match expected scale

```
Solution 1: Check if transformation happens on client
  - Web app slider shows 0-100%
  - API might use different scale internally
  - Record actual API values, not web app display

Solution 2: Check response structure
  - IBlindPosition might nest data deeper
  - Example: { type: "IBlindPosition", data: { position: 50 } }
  - Expand JSON tree in DevTools

Solution 3: Device might have custom calibration
  - Record exact values as-is
  - Note any patterns (linear, non-linear, capped)
```

### Problem: Cannot see Stop command

```
Solution 1: Blind might not be moving
  - Verify TaskExecution = 1 before clicking Stop
  - Try longer distance (fully open → click Stop → should be mid-movement)

Solution 2: Stop might use same SetBlindPosition with current value
  - When Stop clicked, look for POST with same position value
  - Note timestamp of when you clicked Stop

Solution 3: Stop might be SetBlindPositionSimple
  - Look for POST with taskType="SetBlindPositionSimple"
  - This might appear under different timing
```

---

## NEXT STEPS AFTER VALIDATION

1. Fill out the Result Template (Part 9) with your findings
2. Commit your results to GitHub as VALIDATION_RESULTS.md
3. Update EVIDENCE_MATRIX_HA.md Unknown sections with validated values
4. Proceed to IMPLEMENTATION_PLAN_HA.md Phase 1 (Data Models)

**Do NOT begin implementation until all 3 blocking unknowns are resolved.**
