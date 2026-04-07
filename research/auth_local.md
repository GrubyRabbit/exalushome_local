# ExalusHome Local/Direct Authentication & Connection

## Overview
Local connection uses WebSocket protocol to communicate directly with ExalusHome controller on the local network.
No internet or cloud broker required.

---

## LocalNetworkExalusConnectionService

### Default Configuration
```typescript
class LocalNetworkExalusConnectionService {
    private _address: string;           // Controller IP address
    private _port: string = "81";       // WebSocket port (default 81)
    private _pin: string;               // Controller PIN
    private _serial: string;            // Controller serial number
    private _pingInterval: number = 5000;  // Ping every 5 seconds
}
```

**Key Finding:** Default port is **81** (not 80, not 443)

---

## AuthorizationInfo (Same as Remote)

```typescript
class AuthorizationInfo {
    serialNumber: string;  // Controller serial number
    pin: string;          // Controller PIN
    
    // Properties
    SerialNumber: string;
    PIN: string;
}
```

### Credential Sources
For local mode:
1. **Serial Number**: Can be found on controller device label or in app settings
2. **PIN**: Default is usually "0000", can be changed in controller settings

---

## Connection Lifecycle

### Step 1: Prepare Authentication
```typescript
const authInfo = new AuthorizationInfo(
    "ABC123DEF456",  // Serial number
    "0000"           // PIN
);
```

### Step 2: Connect to Local Controller
```typescript
const localService = new LocalNetworkExalusConnectionService();

// Connect to controller IP on port 81
const result = await localService.ConnectAsync("192.168.1.100");
// or
const result = await localService.ConnectAndAuthorizeAsync(authInfo);
```

### Connection Details
- **WebSocket URL:** `ws://controller_ip:81`
- **Protocol:** Custom binary protocol over WebSocket
- **TLS/SSL:** Not used (plain WebSocket)
- **Authentication:** Sent after connection established

---

## Authorization Process

### Built-in Validation
The service includes endpoint-based auth validation:

```typescript
private async checkIfAuthInfoIsCorrectAsync(authInfo: AuthorizationInfo): Promise<boolean> {
    // Calls HTTP endpoint on controller
    const url = `http://${window.location.hostname}/controller_info`;
    const response = await fetch(url, { method: 'GET' });
    
    if (response.ok) {
        const text = await response.text();
        // Expected format: "SERIAL:PIN"
        return text === `${authInfo.SerialNumber}:${authInfo.PIN}`;
    }
    return false;
}
```

**Important:** There's also an HTTP endpoint `http://controller_ip/controller_info` that returns `SERIAL:PIN` format.
This could be used for discovery or validation.

---

## WebSocket Communication

### Frame Structure
Same `IDataFrame<T>` as remote mode:

```typescript
interface IDataFrame<T> {
    Resource?: string;
    TransactionId?: string;
    Data?: T;
    Status?: Status;
    Method?: Method;
}
```

### Example: Get Device State
```json
// Request (sent over WebSocket)
{
    "Resource": "/devices/abc123/state",
    "TransactionId": "local_001",
    "Method": 0  // Get
}

// Response (received from controller)
{
    "Resource": "/devices/abc123/state",
    "TransactionId": "local_001",
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

---

## Keep-Alive (Ping/Pong)

Local connection uses custom ping mechanism:

```typescript
async PingControllerAsync(): Promise<boolean> {
    if (this.socket?.readyState !== WebSocket.OPEN)
        return false;
    
    // Only ping if no data received recently
    if (Date.now() - this._lastReceivedPacketTime < this._pingInterval)
        return false;
    
    const frame = new DataFrame();
    frame.Resource = "/system/ping";
    frame.Method = Method.Get;  // HTTP GET
    
    const result = await this.SendAndWaitForResponseAsync(
        frame,
        timeout: 2000,
        useCache: false
    ).then(() => true).catch(() => false);
    
    return result;
}
```

**Ping Interval:** 5000ms (5 seconds)
**Ping Timeout:** 2000ms (2 seconds)
**Ping Resource:** `/system/ping`

---

## Event Subscriptions

Same as remote mode:

```typescript
// Connection state changes
localService.OnConnectionStateChangedEvent().subscribe((state: ConnectionState) => {
    console.log("State:", state);
});

// Data received (unsolicited updates)
localService.OnDataReceivedEvent().subscribe((frame: IDataFrame<any>) => {
    console.log("Update:", frame.Resource);
});

// Errors
localService.OnErrorOccuredEvent().subscribe(([sender, error]) => {
    console.error(sender, error);
});
```

---

## Limitations vs. Remote

1. **No Streams**: `SendAndHandleStreamAsync()` returns error
   ```typescript
   SendAndHandleStreamAsync(dataFrame, streamHandler, logTransmission) {
       return Promise.reject(
           new Error("Streams are not supported over local network connection.")
       );
   }
   ```

2. **Single Endpoint**: No broker failover. If controller is offline, connection fails.

3. **LAN-Only**: Cannot reach controller from outside local network.

4. **No Multi-Broker**: Direct connection to single IP:port.

---

## Session Management

Like remote mode, but simpler:

```typescript
// Automatic session restoration on wake from sleep
appState.OnAppStateChanged().subscribe((state) => {
    if (state === AppState.ExitedLowPowerMode || 
        state === AppState.ReturnedFromSuspension) {
        this.RestoreConnectionAsync();
        session?.RestoreSessionAsync();
    }
});
```

---

## Caching

Response caching supported (same as remote):

```typescript
// Cache recent responses
const response = await localService.SendAndWaitForResponseAsync(
    frame,
    timeout: 5000,
    useCache: true  // Return cached if available
);
```

---

## Configuration & Advanced

### Logging
```typescript
localService.EnablePacketsLogging();   // Debug: log all frames
localService.DisablePacketsLogging();  // Production: disable
```

### Service Name
```typescript
static readonly ServiceName = "LocalNetworkExalusConnectionService";
```

---

## Discovery Method

**NOT documented in source code**. Options for HA integration:

1. **Manual IP entry** in config flow
2. **mDNS/Bonjour discovery** if controller advertises itself
3. **Network scanning** for default port 81
4. **QR code scanning** from controller
5. **User provides from router DHCP list**

**Action Item:** Test web app to determine how official app discovers controllers.

---

## Known Endpoints

Based on source code analysis:

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/system/ping` | GET | Keep-alive ping |
| `/controller_info` | GET | Get controller serial:pin (returns `SERIAL:PIN`) |
| `/devices/*` | GET/POST | Device state and commands |
| (others) | ? | TBD from web app sniffing |

---

## Known Issues & TODOs

- [ ] Confirm default port is always 81 (not configurable?)
- [ ] Verify HTTP endpoint format (`/controller_info`)
- [ ] Determine device discovery mechanism
- [ ] Confirm WebSocket is unencrypted (`ws://` not `wss://`)
- [ ] Extract all API endpoints from web app
- [ ] Document error codes/status meanings
- [ ] Confirm ping interval is always 5000ms
- [ ] Determine if local connection auto-falls-back to remote
