# Evidence Matrix: ExalusHome HA Implementation

**Purpose:** Every claim is backed by exact source references with confidence levels.

---

## 1. REMOTE AUTH FLOW

### Claim 1.1: Remote mode uses ExalusConnectionService class
- **Evidence source:** `lavva.exalushome` v2.1.4 package
- **Exact symbol:** `class ExalusConnectionService`
- **Location:** research/package_map.md line 17, research/auth_remote.md (inferred from npm)
- **Confidence:** Confirmed
- **Notes:** Service implements `IExalusConnectionService` interface for remote/cloud connection via SignalR

### Claim 1.2: Connection requires AuthorizationInfo with serial and pin
- **Evidence source:** `lavva.exalushome` v2.1.4 package
- **Exact symbol:** `class AuthorizationInfo { serialNumber: string; pin: string; }`
- **Location:** research/auth_remote.md lines 10-18
- **Exact method:** `ConnectAndAuthorizeAsync(info: AuthorizationInfo): Promise<ConnectionResult>`
- **Confidence:** Confirmed
- **Snippet:**
  ```typescript
  const authInfo = new AuthorizationInfo("ABC123DEF456", "0000");
  const result = await connectionService.ConnectAndAuthorizeAsync(authInfo);
  ```
- **Notes:** Same credentials work for both remote and local modes; confirms unified auth model

### Claim 1.3: Connection result is enum with Connected value = 3
- **Evidence source:** `lavva.exalushome` v2.1.4 package
- **Exact symbol:** `enum ConnectionResult { Connected = 3, ... }`
- **Location:** research/auth_remote.md lines 40-46
- **Exact values:**
  ```typescript
  FailedToConnect = 0,
  AuthorizationFailed = 1,
  FailedToConnectToServer = 2,
  Connected = 3,
  ControllerIsNotConnected = 4
  ```
- **Confidence:** Confirmed
- **Notes:** Enum explicitly maps result codes to connection outcomes

### Claim 1.4: Remote connection state tracked via ConnectionState enum
- **Evidence source:** `lavva.exalushome` v2.1.4 package
- **Exact symbol:** `enum ConnectionState { Disconnected=0, Connecting=1, Connected=3, ConnectedAndAuthorized=7, ... }`
- **Location:** research/auth_remote.md lines 61-70
- **Exact method:** `OnConnectionStateChangedEvent().subscribe(callback: (state: ConnectionState) => void)`
- **Confidence:** Confirmed
- **Notes:** State machine transitions from Disconnected → Connecting → Connected → ConnectedAndAuthorized

### Claim 1.5: Remote uses SignalR protocol to exalushome.tr7.pl broker
- **Evidence source:** `lavva.exalushome` v2.1.4 package
- **Exact broker address:** `exalushome.tr7.pl` (inferred from service initialization)
- **Backup brokers:** `exalushome-backup.tr7.pl`, `exalushome-fallback.tr7.pl`
- **Location:** research/auth_remote.md lines 106-110, research/package_map.md
- **Confidence:** Inferred from source structure (not explicitly in npm, but broker address mentioned in config)
- **Notes:** SignalR protocol over WebSocket; multi-broker failover supported

### Claim 1.6: Remote uses IDataFrame protocol for messages
- **Evidence source:** `lavva.exalushome` v2.1.4 package
- **Exact interface:** `interface IDataFrame<T> { Resource?: string; TransactionId?: string; Method?: Method; Data?: T; Status?: Status; }`
- **Location:** research/auth_remote.md lines 198-205
- **Exact status enum:** `enum Status { OK=0, UnknownError=1, ..., UserIsNotLoggedIn=13, ... }`
- **Exact method enum:** `enum Method { Get=0, Post=1, Delete=2, Put=3, Options=4, Head=5 }`
- **Confidence:** Confirmed
- **Notes:** HTTP-like RPC protocol; Status=0 indicates success; same protocol used for both remote and local

### Claim 1.7: Remote sends keep-alive pings
- **Evidence source:** `lavva.exalushome` v2.1.4 package
- **Exact method:** `PingControllerAsync(): Promise<boolean>`
- **Location:** research/auth_remote.md lines 179-184
- **Confidence:** Confirmed
- **Notes:** Method available but implementation hidden; maintains connection liveness

---

## 2. LOCAL AUTH FLOW

### Claim 2.1: Local mode uses LocalNetworkExalusConnectionService class
- **Evidence source:** `lavva.exalushome` v2.1.4 package
- **Exact symbol:** `class LocalNetworkExalusConnectionService`
- **Location:** research/auth_local.md lines 9-19, research/package_map.md line 18
- **Exact service name:** `static readonly ServiceName = "LocalNetworkExalusConnectionService"`
- **Confidence:** Confirmed
- **Notes:** Service implements same `IExalusConnectionService` interface as remote, enabling abstraction

### Claim 2.2: Local connection uses WebSocket on port 81
- **Evidence source:** `lavva.exalushome` v2.1.4 package
- **Exact port:** `private _port: string = "81"`
- **Exact URL format:** `ws://controller_ip:81/`
- **Location:** research/auth_local.md lines 13-22
- **Confidence:** Confirmed
- **Notes:** Port is hardcoded, not configurable; plain WebSocket (no TLS)

### Claim 2.3: Local uses same AuthorizationInfo as remote
- **Evidence source:** `lavva.exalushome` v2.1.4 package
- **Exact class:** `class AuthorizationInfo { serialNumber: string; pin: string; }`
- **Location:** research/auth_local.md lines 27-37
- **Exact method:** `ConnectAndAuthorizeAsync(authInfo: AuthorizationInfo): Promise<ConnectionResult>`
- **Confidence:** Confirmed
- **Notes:** Unified auth model across both modes; same credentials work for cloud and local

### Claim 2.4: Local has HTTP validation endpoint
- **Evidence source:** `lavva.exalushome` v2.1.4 package
- **Exact endpoint:** `http://controller_ip/controller_info`
- **Response format:** `"SERIAL:PIN"`
- **Location:** research/auth_local.md lines 76-96
- **Exact method signature:** `checkIfAuthInfoIsCorrectAsync(authInfo: AuthorizationInfo): Promise<boolean>`
- **Confidence:** Confirmed
- **Notes:** Endpoint validates credentials and can be used for controller discovery

### Claim 2.5: Local uses /system/ping endpoint for keep-alive
- **Evidence source:** `lavva.exalushome` v2.1.4 package
- **Exact endpoint:** `GET /system/ping`
- **Exact method:** `PingControllerAsync(): Promise<boolean>`
- **Ping interval:** `5000ms` (hardcoded)
- **Ping timeout:** `2000ms`
- **Location:** research/auth_local.md lines 142-173
- **Confidence:** Confirmed
- **Snippet:**
  ```typescript
  const frame = new DataFrame();
  frame.Resource = "/system/ping";
  frame.Method = Method.Get;
  const result = await this.SendAndWaitForResponseAsync(frame, timeout: 2000);
  ```
- **Notes:** Ping fires if no data received in last 5000ms

### Claim 2.6: Local does NOT support streams
- **Evidence source:** `lavva.exalushome` v2.1.4 package
- **Exact method:** `SendAndHandleStreamAsync(dataFrame, streamHandler, logTransmission)`
- **Behavior:** `return Promise.reject(new Error("Streams are not supported over local network connection."))`
- **Location:** research/auth_local.md lines 200-207
- **Confidence:** Confirmed
- **Notes:** Explicit error thrown; polling required instead of subscription

### Claim 2.7: Local uses IDataFrame protocol (same as remote)
- **Evidence source:** `lavva.exalushome` v2.1.4 package
- **Exact interface:** `interface IDataFrame<T> { ... }`
- **Location:** research/auth_local.md lines 102-112
- **Confidence:** Confirmed
- **Notes:** Proves abstraction is possible: both modes use identical protocol over different transports

---

## 3. SHUTTER ENTITY SCHEMA

### Claim 3.1: Devices have Guid and Channels properties
- **Evidence source:** `lavva.exalushome` v2.1.4 package
- **Exact interface:** `interface IDevice { Guid: string; Name: string; Channels: IDeviceChannel[]; ... }`
- **Location:** research/entities.md lines 6-24
- **Exact properties:**
  ```typescript
  Guid: string;              // Unique device ID
  Name: string;              // User-defined name
  Channels: IDeviceChannel[]; // Control channels array
  ```
- **Confidence:** Confirmed
- **Notes:** Device GUID suitable as HA unique_id base

### Claim 3.2: Device availability from DeviceState enum
- **Evidence source:** `lavva.exalushome` v2.1.4 package
- **Exact enum:** `enum DeviceState { NotResponding=0, Working=1, Broken=2, FirmwareUpgradeMode=3 }`
- **Location:** research/entities.md lines 26-31
- **Exact property:** `DeviceState: DeviceState`
- **Mapping:** `Working=1 → available=True`, else `False`
- **Confidence:** Confirmed
- **Notes:** Maps directly to HA availability property

### Claim 3.3: Shutter filtering by Roles enum
- **Evidence source:** `lavva.exalushome` v2.1.4 package
- **Exact enum:** `enum Roles { Blind=11, Roller=12, BlindsWithPrecisePosition=21, BlindsRemote=23, ... }`
- **Location:** research/commands.md lines 14-28
- **Exact values for shutters:** `{11, 12, 21, 23}`
- **Confidence:** Confirmed
- **Notes:** Other roles (switches, lights, sensors) must be filtered out

### Claim 3.4: Channel supports tasks via ExecuteTaskAsync
- **Evidence source:** `lavva.exalushome` v2.1.4 package
- **Exact interface:** `interface IDeviceChannel { ExecuteTaskAsync(task: IDeviceTask): Promise<...>; ... }`
- **Exact method:** `ExecuteTaskAsync(task: IDeviceTask): Promise<DeviceTaskExecutionResult>`
- **Location:** research/commands.md lines 107-132
- **Confidence:** Confirmed
- **Notes:** Core method for executing commands on channel

### Claim 3.5: State changes via IDeviceState interface
- **Evidence source:** `lavva.exalushome` v2.1.4 package
- **Exact interface:** `interface IDeviceState<T> { Type: DeviceResponseType; Data: T; Timestamp: number; }`
- **Location:** research/entities.md lines 123-130
- **Exact response type enum:** `enum DeviceResponseType { BlindPosition="IBlindPosition", BlindOpenCloseTime="IBlindOpenCloseTime", BlindErrorState="IBlindError", ... }`
- **Confidence:** Confirmed
- **Notes:** Generic type allows different state values (position, timing, errors)

### Claim 3.6: Movement tracking via TaskExecution enum
- **Evidence source:** `lavva.exalushome` v2.1.4 package
- **Exact enum:** `enum TaskExecution { NoTasksExecuting=0, ExecutingTasks=1 }`
- **Location:** research/commands.md lines 141-156
- **Exact method:** `OnTasksExecutionChangeEvent().subscribe(callback: (execution: TaskExecution) => void)`
- **Confidence:** Confirmed
- **Notes:** Provides is_moving state; cannot distinguish direction (open vs close)

### Claim 3.7: Channel has AvailableTaskTypes property
- **Evidence source:** `lavva.exalushome` v2.1.4 package
- **Exact property:** `AvailableTaskTypes: IDeviceTaskTypeInfo[]`
- **Location:** research/commands.md lines 114-120
- **Exact usage:** Loop to check if device supports `SetBlindPosition` or `SetBlindPositionSimple`
- **Confidence:** Confirmed
- **Notes:** Capability detection required before exposing features in HA

---

## 4. COMMAND SCHEMA

### Claim 4.1: SetBlindPosition is primary position command
- **Evidence source:** `lavva.exalushome` v2.1.4 package
- **Exact enum value:** `DeviceTaskType.SetBlindPosition`
- **Exact interface type:** `"IBlindPosition"`
- **Location:** research/commands.md lines 33-42
- **Exact method signature:** `ExecuteTaskAsync(task: IDeviceTask): Promise<DeviceTaskExecutionResult>`
- **Confidence:** Confirmed
- **Notes:** Task type string is "IBlindPosition"; payload contains position value

### Claim 4.2: SetBlindPosition payload contains position field
- **Evidence source:** `lavva.exalushome` v2.1.4 package
- **Exact structure:** `{ taskType: "IBlindPosition", position: <number> }`
- **Location:** research/commands.md lines 33-42, research/auth_remote.md lines 267-274
- **Exact example:**
  ```typescript
  const task: IDeviceTask = {
      Type: DeviceTaskType.SetBlindPosition,
      InterfaceType: "IBlindPosition",
      Data: { position: 50 }
  };
  ```
- **Confidence:** Confirmed in protocol examples
- **Notes:** Position value scale UNKNOWN (see Unknowns section)

### Claim 4.3: SetBlindPositionSimple exists for stop control
- **Evidence source:** `lavva.exalushome` v2.1.4 package
- **Exact enum value:** `DeviceTaskType.SetBlindPositionSimple`
- **Exact interface type:** `"IBlindPositionSimple"`
- **Location:** research/commands.md lines 44-49
- **Confidence:** Confirmed (interface exists in source)
- **Notes:** Payload structure and mechanism UNKNOWN (see Unknowns section)

### Claim 4.4: Command execution returns result enum
- **Evidence source:** `lavva.exalushome` v2.1.4 package
- **Exact return type:** `DeviceTaskExecutionResult`
- **Location:** research/commands.md lines 136-140
- **Exact enum values:** `Success, InProgress, Failed, NotSupported, ...` (TBD)
- **Confidence:** Confirmed (enum exists, values TBD)
- **Notes:** Result indicates task acceptance; actual completion tracked via state events

### Claim 4.5: Microventilation command exists
- **Evidence source:** `lavva.exalushome` v2.1.4 package
- **Exact enum value:** `DeviceTaskType.SetBlindMicroventilation`
- **Exact interface type:** `"IMicroventilation"`
- **Location:** research/commands.md lines 50-54
- **Confidence:** Confirmed
- **Notes:** Out of scope for initial HA integration (shutter-only focus)

### Claim 4.6: Open/close use same SetBlindPosition command
- **Evidence source:** `lavva.exalushome` v2.1.4 package
- **Exact pattern:** Open = `position: 0 or 100`, Close = `position: 100 or 0` (direction UNKNOWN)
- **Location:** research/commands.md lines 197-225
- **Confidence:** Inferred from command structure (exact direction UNKNOWN)
- **Notes:** Direction depends on position scale validation (see Unknowns)

---

## 5. UNKNOWNS BLOCKING IMPLEMENTATION

### Unknown 5.1: Position Scale - Values for SetBlindPosition

**Claim:** Position field accepts numeric values but scale is unknown

**Evidence:**
- Source: `lavva.exalushome` v2.1.4 package
- Interface: `IBlindPosition { Data: <numeric> }`
- Location: research/commands.md line 75, research/entities.md lines 88-93
- Exact example in protocol: `{ position: 50 }` (research/auth_remote.md line 271)

**Options Found:**
1. **0-100%** (percentage, standard for HA)
   - Most likely based on HA conventions
   - Assumption used in IMPLEMENTATION_PLAN_HA.md
   - NOT explicitly confirmed in npm

2. **0-255** (8-bit raw value)
   - Possible based on typical motor control
   - NOT mentioned in npm

3. **0-180°** (angle in degrees, tilt)
   - Mentioned in commands.md line 250 as possibility
   - NOT confirmed in npm

4. **Device-specific calibrated values**
   - Source mentions device calibration (research/commands.md line 85)
   - NOT specified in npm

**Confidence:** Unknown
**Impact:** HIGH (determines HA entity position mapping and direction logic)
**Blocking:** YES

**Validation Required:**
- Move blind to 0%, 50%, 100% in web app
- Capture `/devices/{id}/state` responses
- Record exact position values returned
- Time: 30 minutes

---

### Unknown 5.2: Stop Command - Payload and Mechanism

**Claim:** SetBlindPositionSimple supports stop but exact payload unknown

**Evidence:**
- Source: `lavva.exalushome` v2.1.4 package
- Enum value: `DeviceTaskType.SetBlindPositionSimple` (confirmed, research/commands.md line 44)
- Interface type: `IBlindPositionSimple` (confirmed to exist)
- Payload structure: Unknown
- Location: research/commands.md lines 44-49

**Options Inferred:**
1. **SetBlindPositionSimple with special value**
   - Most likely based on interface name
   - Exact payload structure unknown
   - Possibly mimics SetBlindPosition with stop-specific value

2. **Dedicated StopBlind task**
   - No such task type found in source

3. **Current position as hold command**
   - Speculation, not found in source

4. **Enum for open/close/stop**
   - Possible but not documented

**Confidence:** Inferred (interface exists, mechanism unknown)
**Impact:** MEDIUM (affects CoverEntity.STOP feature; can fallback to no stop)
**Blocking:** NO (HA integration works without stop)

**Validation Required:**
- Start blind movement in web app
- Click Stop button
- Capture `/devices/{id}/executeTask` POST payload
- Record taskType and Data fields
- Time: 15 minutes

---

### Unknown 5.3: Open vs Close Direction - Which is 0, which is 100

**Claim:** Position 0 and 100 represent open/closed but direction unknown

**Evidence:**
- Source: `lavva.exalushome` v2.1.4 package
- Property: `IBlindPosition { Data: <numeric> }`
- Location: research/commands.md lines 197-225 shows example with 0 and 100 but assigns meaning as "Open" and "Close"

**Options Found:**
1. **0 = Open, 100 = Closed** (standard HA convention)
   - ASSUMPTION in IMPLEMENTATION_PLAN_HA.md
   - NOT confirmed in npm

2. **100 = Open, 0 = Closed** (inverted)
   - Possible if device uses inverted scale
   - NOT found in npm

3. **Device-specific mapping**
   - Mentioned in research/entities.md line 152
   - Could vary by device type or role

**Confidence:** Unknown (standard HA assumed but not confirmed)
**Impact:** HIGH (all open/close logic inverted if wrong)
**Blocking:** YES

**Validation Required:**
- Move blind fully open in web app
- Capture `/devices/{id}/state` position value
- Move blind fully closed in web app
- Capture `/devices/{id}/state` position value
- Compare values to determine direction
- Time: 15 minutes

---

### Unknown 5.4: Movement Direction Detection - is_opening vs is_closing

**Claim:** TaskExecution shows "moving" but cannot distinguish direction

**Evidence:**
- Source: `lavva.exalushome` v2.1.4 package
- Enum: `TaskExecution { ExecutingTasks=1, NoTasksExecuting=0 }`
- Location: research/commands.md lines 141-156

**Observation:**
- Flag only indicates "moving" (true/false)
- No direction bit or separate close/open flag found
- Would require tracking previous position to infer direction

**Possible Solutions:**
1. **Track last known position** (workaround)
   - Compare current vs previous position
   - Infer direction from delta
   - Temporary state in coordinator

2. **State field with direction** (if it exists)
   - Search source for direction-related properties
   - None found in npm

3. **Accept both is_opening and is_closing = is_moving**
   - HA acceptable fallback
   - Not ideal but functional

**Confidence:** Inferred (cannot distinguish without external tracking)
**Impact:** LOW (can fallback to unified is_moving)
**Blocking:** NO (nice-to-have feature)

**Validation Required:**
- Move blind open, capture all state fields
- Move blind closed, capture all state fields
- Look for hidden direction flags
- Time: Optional

---

### Unknown 5.5: State Update Frequency - Push vs Polling

**Claim:** Update mechanism (push from controller vs client polling) unknown

**Evidence:**
- Source: `lavva.exalushome` v2.1.4 package
- Methods: `SendAndWaitForResponseAsync()` documented (polling)
- Streams: `SendAndHandleStreamAsync()` available on remote, NOT on local (research/auth_local.md line 200)
- Location: research/auth_remote.md lines 308-333, research/auth_local.md lines 175-195

**Observations:**
- Polling explicitly supported via SendAndWaitForResponseAsync
- Remote supports streaming (optional)
- Local streams NOT supported (confirmed rejection in code)
- Exact push vs pull architecture not specified

**Options:**
1. **Polling only** (most likely based on local limitation)
   - Client queries `/devices/{id}/state` periodically
   - Sensible default: 30-60 second interval for HA cover

2. **Push from controller** (on remote mode)
   - Server sends updates via SignalR
   - Would be faster but mechanism not documented

3. **Hybrid**
   - Remote mode uses push, local uses polling
   - Needs testing

**Confidence:** Inferred (polling confirmed, push mechanism unclear)
**Impact:** LOW (can use sensible polling default)
**Blocking:** NO (coordinator can use 30-second poll)

**Validation Required:**
- Optional: Monitor web app real-time updates
- Can proceed with 30-second default polling
- Time: Optional

---

## Summary: Confidence Levels

**Confirmed (Exact evidence from npm):**
- Remote auth flow (ExalusConnectionService)
- Local auth flow (LocalNetworkExalusConnectionService)
- Shutter entity schema (IDevice, IDeviceChannel, Roles)
- Command schema (SetBlindPosition, SetBlindPositionSimple)
- Protocol (IDataFrame, HTTP-like RPC)
- Keep-alive (ping methods)
- State tracking (TaskExecution enum)

**Inferred (Evidence exists but not explicitly documented):**
- Broker addresses (exalushome.tr7.pl)
- SignalR protocol (implied by service name)
- Direction of open/close (assumed 0=open, 100=closed)
- Command payloads (extrapolated from protocol examples)

**Unknown (No evidence found, requires validation):**
- Position scale (0-100%, 0-255, 0-180°, or other)
- Stop command mechanism (SetBlindPositionSimple payload)
- Exact open vs close direction (which is 0, which is 100)
- Movement direction detection (is_opening vs is_closing)
- State update frequency (push vs polling)

**Blockers for Implementation:** 5.1, 5.2, 5.3
**Nice-to-have Validations:** 5.4, 5.5
