# ExalusHome Authentication & Protocol

## Remote Mode: AuthorizationInfo

### Interface Definition
```typescript
serialNumber: string;
pin: string;
constructor(serialNumber: string, pin: string);
SerialNumber: string;
PIN: string;
```

### Connection Process
1. Create `AuthorizationInfo` with credentials
2. Call `ExalusConnectionService.ConnectAndAuthorizeAsync(authInfo)`
3. Service initiates SignalR connection to broker
4. Broker negotiates protocol version
5. Client sends credentials over SignalR
6. Server returns authorization result
7. Connection established and ready for commands

### Credential Requirements
- Username / Email
- Password
- PIN (device-specific)
- Serial Number (controller identifier)

### Server Broker Selection
The library supports multiple server brokers for high availability:
- Primary broker
- Secondary broker (if primary fails)
- Automatic failover with exponential backoff

---

## Local Mode: Local AuthorizationInfo

### Connection Requirements
- Controller IP address
- Controller port (WebSocket port, default unknown)
- PIN (same as controller PIN)
- Serial Number (same as controller identifier)

### Connection Process
1. Create local auth info with IP, port, PIN, serial
2. Call `LocalNetworkExalusConnectionService.ConnectAndAuthorizeAsync(authInfo)`
3. Service initiates WebSocket connection to controller
4. Sends initialization frame with PIN and serial
5. Controller validates credentials
6. Connection established
7. Subscription to device state updates possible

### Differences from Remote
- No internet required
- No cloud broker needed
- Lower latency
- Limited to local network
- No multi-broker failover
- Simpler auth (PIN only, no password)

---

## DataFrame Protocol

### Purpose
Universal message container for all communication (both remote and local)

### Structure
```typescript
Resource?: string;
TransactionId?: string;
Data?: T;
Status?: Status;
Method?: Method;
```

### Payload Type
All frames carry generic `<T>` payload:
```typescript
interface IDataFrame<T> {
  // Generic payload
  data: T;
  // Metadata
  // timestamp?: number;
  // requestId?: string;
  // responseId?: string;
}
```

### Examples

#### State Request
```json
{
  "command": "GetDeviceState",
  "deviceGuid": "12345-abcde",
  "timestamp": 1234567890
}
```

#### State Response
```json
{
  "deviceGuid": "12345-abcde",
  "states": [
    {
      "type": "IBlindPosition",
      "value": 75,
      "timestamp": 1234567890
    }
  ]
}
```

#### Command (Set Blind Position)
```json
{
  "command": "ExecuteTask",
  "deviceGuid": "12345-abcde",
  "taskType": "IBlindPosition",
  "position": 50
}
```

---

## Connection State Machine

### ConnectionState Enum
```
- Disconnected = 0
- Connecting = 1
- Connected = 3
- Disconnecting = 4
- Failed = 5
- Reconnecting = 6
- ConnectedAndAuthorized = 7
```

### State Transitions

```
[Disconnected] -> Connecting -> Connected -> Authorizing -> Authorized
                                    ↓
                            [Connection Failed]
                                    ↓
                            [Retry with Backoff]

[Authorized] -> [Ping Failure] -> Reconnecting -> ...

[Authorized] -> DisconnectAsync() -> Disconnected
```

---

## Keep-Alive & Ping

Both connection modes implement ping/pong keep-alive:

### Remote Mode (SignalR)
- Ping interval: TBD (likely 30-60 seconds)
- Timeout: TBD (likely 2-3 minutes)
- Method: SignalR hub method call
- Response: Pong event

### Local Mode (WebSocket)
- Ping interval: Configured in service
- Timeout: Configurable
- Method: Custom WebSocket ping frame
- Response: WebSocket pong frame

---

## Session Management

Both connection modes maintain session state:

### Session Data
- Connection ID
- Authorization info
- Server/Controller info
- Cache of recent responses

### Session Restoration
If connection drops unexpectedly:
1. Detect disconnection
2. Wait exponential backoff
3. Attempt automatic reconnection
4. Restore cached session if available
5. Re-authorize if needed
6. Resume operations

---

## Error Handling

### Error Types
- Network errors (timeout, refused)
- Authentication errors (invalid PIN, wrong password)
- Protocol errors (malformed frame)
- Timeout errors (no response)
- Session errors (session expired)

### Error Event
```typescript
service.OnErrorOccuredEvent().subscribe((sender: string, errorMessage: string) => {
  // Handle error: sender is service name, errorMessage describes issue
});
```

---

## Known Ports & Defaults

### Remote Mode
- Broker: `exalushome.tr7.pl` (as seen in web app URL)
- Protocol: HTTPS (443)
- SignalR path: `/hubs/controller` or similar (TBD)

### Local Mode
- Host: `controller_ip`
- Port: Unknown (to be determined from network analysis)
- Protocol: WebSocket (ws://)
- TLS: Unclear (may be ws:// or wss://)

---

## TODO: Validate from Source

- [ ] Extract exact AuthorizationInfo fields
- [ ] Extract exact DataFrame structure
- [ ] Find default WebSocket port for local mode
- [ ] Extract exact connection state values
- [ ] Extract exact error codes/types
- [ ] Find SignalR hub method names
- [ ] Find device state update subscription mechanism
