# ExalusHome Remote/Cloud Authentication & Connection

## Overview
Remote connection uses Microsoft SignalR protocol with cloud broker for device control over the internet.

---

## AuthorizationInfo Class

```typescript
class AuthorizationInfo {
    serialNumber: string;  // Controller serial number
    pin: string;          // Controller PIN (default is usually "0000")
    
    // Properties (same values, different case convention)
    SerialNumber: string;
    PIN: string;
}
```

### Usage
```typescript
const authInfo = new AuthorizationInfo(
    "ABC123DEF456",  // Controller serial number
    "0000"           // Controller PIN
);

// Connect and authorize
const result = await connectionService.ConnectAndAuthorizeAsync(authInfo);
if (result === ConnectionResult.Connected) {
    // Ready to send commands
}
```

---

## ConnectionResult Enum

```typescript
enum ConnectionResult {
    FailedToConnect = 0,
    AuthorizationFailed = 1,
    FailedToConnectToServer = 2,
    Connected = 3,
    ControllerIsNotConnected = 4
}
```

**Interpretation:**
- `Connected` = Success, ready for commands
- `AuthorizationFailed` = Wrong PIN or serial number
- `ControllerIsNotConnected` = Controller offline at broker
- `FailedToConnectToServer` = Cannot reach broker servers
- `FailedToConnect` = Generic connection failure

---

## ConnectionState Enum

```typescript
enum ConnectionState {
    Disconnected = 0,
    Connecting = 1,
    Connected = 3,
    Disconnecting = 4,
    Failed = 5,
    Reconnecting = 6,
    ConnectedAndAuthorized = 7
}
```

**State Flow:**
```
Disconnected
    ↓
Connecting (SignalR negotiation)
    ↓
Connected (socket open, not yet authorized)
    ↓
ConnectedAndAuthorized (ready for commands)
    ↓
[Operations]
    ↓
Disconnecting
    ↓
Disconnected
```

**Error Path:**
```
Connected → Failed → Reconnecting → Connecting → [retry]
```

---

## ExalusConnectionService (Remote Implementation)

### Initialization
```typescript
const service = new ExalusConnectionService();
// Dependencies injected: logging, app state, configuration caching
```

### Configuration
```typescript
// Set cloud broker address (usually: exalushome.tr7.pl)
service.SetServersBrokerAddress("exalushome.tr7.pl");

// Set packets broker (for large data transfers)
service.SetDefaultPacketsBrokerAddress("packets.exalushome.tr7.pl");

// Optional: Enable debug logging
service.EnablePacketsLogging();
```

### Connection Lifecycle

#### Step 1: Connect to Broker
```typescript
const result = await service.ConnectAsync("exalushome.tr7.pl");
if (result !== ConnectionResult.Connected) {
    console.error("Failed to connect to broker");
}
```

#### Step 2: Authorize with Credentials
```typescript
const authInfo = new AuthorizationInfo("SERIAL", "PIN");
const authorized = await service.AuthorizeAsync(authInfo);
if (!authorized) {
    console.error("Authorization failed - wrong PIN or serial");
}
```

#### Step 3 (Combined): Connect and Authorize Atomically
```typescript
const authInfo = new AuthorizationInfo("SERIAL", "PIN");
const result = await service.ConnectAndAuthorizeAsync(authInfo);
switch (result) {
    case ConnectionResult.Connected:
        // Ready
        break;
    case ConnectionResult.AuthorizationFailed:
        // Wrong credentials
        break;
    // etc.
}
```

### Event Subscriptions

#### Connection State Changes
```typescript
service.OnConnectionStateChangedEvent().subscribe((newState: ConnectionState) => {
    console.log(`Connection state: ${newState}`);
    // Update UI, trigger reconnection logic, etc.
});
```

#### Data Received
```typescript
service.OnDataReceivedEvent().subscribe((frame: IDataFrame<any>) => {
    console.log(`Received frame for resource: ${frame.Resource}`);
    // Process unsolicited updates from server
});
```

#### Errors
```typescript
service.OnErrorOccuredEvent().subscribe(([sender, errorMsg]) => {
    console.error(`[${sender}] ${errorMsg}`);
    // Log, alert user, trigger recovery
});
```

### Keep-Alive
```typescript
// Periodic ping to keep connection alive
const pongReceived = await service.PingControllerAsync();
if (!pongReceived) {
    console.warn("Ping failed - connection may be broken");
    // Trigger reconnection
}
```

### Disconnection
```typescript
await service.DisconnectAsync();
// Connection state → Disconnecting → Disconnected
```

---

## DataFrame Protocol (HTTP-like)

### Structure
```typescript
interface IDataFrame<T> {
    Resource?: string;       // API resource path (e.g., "/devices/123/state")
    TransactionId?: string;  // Unique request ID for request-response matching
    Data?: T;                // Payload (generic type, varies by resource)
    Status?: Status;         // Response status code
    Method?: Method;         // HTTP-like method (Get, Post, Put, Delete)
}

enum Status {
    OK = 0,
    UnknownError = 1,
    FatalError = 2,
    WrongData = 3,
    ResourceDoesNotExists = 4,
    NoPermissionToPerformThisOperation = 5,
    SessionHasAlreadyLoggedOnUser = 6,
    OperationNotPermitted = 7,
    NoPermissionsToCallGivenResource = 8,
    ResourceIsNotAvailable = 9,
    Error = 10,
    NoData = 11,
    NotSupportedMethod = 12,
    UserIsNotLoggedIn = 13,
    MultiDataResponseStart = 14,
    MultiDataResponse = 15,
    MultiDataResponseStop = 16
}

enum Method {
    Get = 0,
    Post = 1,
    Delete = 2,
    Put = 3,
    Options = 4,
    Head = 5
}
```

### Example: Fetch Device State
```json
// Request
{
    "Resource": "/devices/abc123/state",
    "TransactionId": "req_001",
    "Method": 0  // Get
}

// Response
{
    "Resource": "/devices/abc123/state",
    "TransactionId": "req_001",
    "Data": {
        "deviceGuid": "abc123",
        "states": [
            {
                "type": "IBlindPosition",
                "data": 75
            }
        ]
    },
    "Status": 0  // OK
}
```

### Example: Execute Command
```json
// Request
{
    "Resource": "/devices/abc123/executeTask",
    "TransactionId": "req_002",
    "Method": 1,  // Post
    "Data": {
        "taskType": "IBlindPosition",
        "position": 50
    }
}

// Response
{
    "Resource": "/devices/abc123/executeTask",
    "TransactionId": "req_002",
    "Data": {
        "executionId": "task_xyz",
        "result": "Success"
    },
    "Status": 0  // OK
}
```

---

## Messaging Patterns

### Request-Response
```typescript
// Send and wait for response with timeout
const response = await service.SendAndWaitForResponseAsync<StateData>(
    frame,
    timeout: 5000,  // milliseconds
    useCache: false,  // true to return cached if available
    logTransmission: true
);
```

### Fire-and-Forget
```typescript
// Send without waiting for response
const sent = await service.SendAsync(frame);
```

### Streaming
```typescript
// Subscribe to stream of updates
await service.SendAndHandleStreamAsync(
    frame,
    {
        Next: (item) => console.log("Update:", item),
        Complete: () => console.log("Stream complete"),
        Error: (err) => console.error("Stream error:", err)
    }
);
```

### Subscriptions
```typescript
// Subscribe to specific resource for updates
const unsubscribe = service.SubscribeTo<StateData>(
    "/devices/abc123/state",
    (frame: IDataFrame<StateData>) => {
        console.log("State update:", frame.Data);
    }
);

// Later: unsubscribe
unsubscribe();
```

---

## Multi-Broker Failover

The service automatically handles failover across multiple cloud brokers:

```typescript
// List of brokers (configured at init time)
const brokers = [
    "exalushome.tr7.pl",
    "exalushome-backup.tr7.pl",
    "exalushome-fallback.tr7.pl"
];

// Service tries each in sequence with exponential backoff
// Transparent to caller
```

---

## Session Restoration

If connection drops unexpectedly:

1. **Detect**: Ping timeout or socket close
2. **Backoff**: Exponential delay (1s, 2s, 4s, 8s, ...)
3. **Reconnect**: Attempt to re-establish connection
4. **Restore**: Reuse cached session if available
5. **Re-authorize**: If session invalid, re-authenticate
6. **Resume**: Continue operations

All transparent to application code.

---

## Configuration Caching

Recent responses cached to reduce server load:

```typescript
// Use cache for repeated queries
const response = await service.SendAndWaitForResponseAsync(
    frame,
    timeout: 5000,
    useCache: true  // Return cached if available
);
```

---

## Known Issues & TODOs

- [ ] Default port for SignalR (likely 443 HTTPS)
- [ ] SignalR hub method names (likely `/hub/controller` or similar)
- [ ] Exact broker server addresses
- [ ] Ping interval timing
- [ ] Session expiration timeout
- [ ] Password field (if remote mode requires username/password in addition to PIN/serial)
