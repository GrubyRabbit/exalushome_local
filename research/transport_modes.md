# ExalusHome Transport Modes

## Overview
ExalusHome supports two fundamentally different connection modes, both abstracted
behind `IExalusConnectionService` interface.

## Remote/Cloud Mode: ExalusConnectionService

### Technology Stack
- **Protocol:** Microsoft SignalR
- **Transport:** WebSocket (primary), Server-Sent Events (fallback)
- **TLS:** Yes (HTTPS)
- **Bidirectional:** Yes

### Connection Flow
1. Client initiates connection to cloud broker
2. Broker negotiates SignalR protocol
3. Client authenticates with credentials
4. Server authorization confirmed
5. Client receives connection state events
6. Continuous ping/pong keep-alive

### Authentication
```typescript
interface AuthorizationInfo {
  // Fields to be determined from source code
  // Expected: username, password, PIN, device serial number
}
```

### Data Exchange
- Request/Response model via SignalR hub methods
- Stream subscriptions for continuous updates
- DataFrames as message containers

### Configuration
- Multiple broker servers for failover
- Configurable server broker address
- Configurable packets broker address

### Connection Lifecycle Events
- `ConnectionStateChangedEvent` — State transitions
- `DataReceivedEvent` — Incoming frames
- `AuthorizationReceivedEvent` — Auth confirmation
- `ErrorOccuredEvent` — Connection errors
- `StreamStartedEvent` — Stream initialization

---

## Local/Direct Mode: LocalNetworkExalusConnectionService

### Technology Stack
- **Protocol:** Custom binary protocol
- **Transport:** WebSocket over TCP
- **TLS:** Unknown (may be plain WebSocket)
- **Bidirectional:** Yes
- **Default Port:** Unknown (to be determined)

### Connection Flow
1. Client establishes WebSocket to `controller_ip:port`
2. Handshake/initialization phase
3. Client authenticates with PIN and device serial
4. Server authorization confirmed
5. Client receives connection state events
6. Continuous ping/pong keep-alive

### Authentication
```typescript
interface LocalAuthInfo {
  // Fields inferred from code:
  pin: string;
  serial: string;
  // Additional fields: TBD
}
```

### Data Exchange
- Request/Response model via WebSocket frames
- Shared `IDataFrame` message format with remote mode
- Cache support for repeated queries

### Connection Lifecycle Events
- `ConnectionStateChangedEvent` — State transitions
- `DataReceivedEvent` — Incoming frames
- `ErrorOccuredEvent` — Connection errors
- `OnMessageReceived` — Low-level frame handling

### Key Differences from Remote Mode
- No multi-broker failover (single IP:port)
- Simpler auth (PIN-based vs. full credentials)
- Lower latency (LAN-only)
- No internet required
- Device discovery method unknown (may require external discovery)

---

## IExalusConnectionService Interface

All connection implementations share this interface:

```typescript
interface IExalusConnectionService {
  // Connection lifecycle
  ConnectAsync(address: string): Promise<ConnectionResult>;
  ConnectAndAuthorizeAsync(info: AuthorizationInfo): Promise<ConnectionResult>;
  DisconnectAsync(): Promise<void>;
  
  // Messaging
  SendAsync(dataFrame: IDataFrame<any>): Promise<boolean>;
  SendAndWaitForResponseAsync<T>(...): Promise<IDataFrame<T>>;
  SendAndHandleResponseAsync<T>(...): Promise<void>;
  SendAndHandleStreamAsync<T>(...): Promise<void>;
  
  // Keep-alive
  PingControllerAsync(): Promise<boolean>;
  
  // Subscriptions
  SubscribeTo<T>(resourceId: string, handler: (data) => void): () => void;
  
  // Events
  OnConnectionStateChangedEvent(): ITypedEvent<ConnectionState>;
  OnDataReceivedEvent(): ITypedEvent<any>;
  OnErrorOccuredEvent(): ITypedEvent<[string, string]>;
  
  // Auth info retrieval
  GetAuthorizationInfo(): AuthorizationInfo | null;
  GetControllerSerialNumber(): string | undefined;
  GetControllerPin(): string | undefined;
}
```

---

## DataFrame Protocol

Both transports communicate via `IDataFrame<T>`:

```typescript
interface IDataFrame<T> {
  // Fields to be reverse-engineered from bundle
  // Expected:
  // - command/method name
  // - request/response ID
  // - payload (generic T)
  // - timestamp
  // - sequence number
}
```

---

## Connection Failure Recovery

Both implementations include:
- Automatic reconnection on network loss
- Exponential backoff retry
- Session restoration
- Configuration caching

---

## Selection Strategy for HA Integration

```python
# Pseudo-code for mode selection
if config.mode == 'remote':
    connection_service = ExalusConnectionService()
    await connection_service.ConnectAndAuthorizeAsync({
        username: config.username,
        password: config.password,
        pin: config.pin,
        serial: config.serial,
    })
elif config.mode == 'local':
    connection_service = LocalNetworkExalusConnectionService()
    await connection_service.ConnectAndAuthorizeAsync({
        pin: config.pin,
        serial: config.serial,
    })
```

---

## Open Questions

1. What is the default port for local WebSocket?
2. Is local WebSocket transport encrypted/TLS?
3. How is the controller discovered on LAN?
4. Can both remote and local be active simultaneously?
5. What are the exact DataFrame structures?
6. Is there a fallback if local connection fails?
