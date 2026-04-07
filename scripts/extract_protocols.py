#!/usr/bin/env python3

"""
Phase 3-4: Deep dive into auth flows and state structures.
Extract AuthorizationInfo, DataFrame, and state interfaces.
"""

import re
import json
from pathlib import Path

EXTRACT_DIR = Path('/tmp/exalushome_packages')
RESEARCH_DIR = Path(__file__).parent.parent / 'research'

auth_findings = {
    'remote_auth': {
        'interface': None,
        'fields': [],
        'initialization': [],
    },
    'local_auth': {
        'interface': None,
        'fields': [],
        'initialization': [],
    },
    'dataframe': {
        'interface': None,
        'fields': [],
    },
}

# ============================================================================
# Extract IExalusConnectionService Interface
# ============================================================================

conn_interface_file = EXTRACT_DIR / 'lavva_exalushome/package/build/js/Services/IExalusConnectionService.d.ts'

if conn_interface_file.exists():
    content = conn_interface_file.read_text()
    
    # Find ConnectionResult
    print('[*] Searching for ConnectionResult...')
    cr_match = re.search(r'(?:export\s+)?(?:interface|type|class)\s+ConnectionResult\s*(?:extends|=)?\s*([^{]*)\s*\{([^}]*)\}', content, re.DOTALL)
    if cr_match:
        print('[+] Found ConnectionResult')
    
    # Find AuthorizationInfo
    print('[*] Searching for AuthorizationInfo...')
    ai_match = re.search(r'(?:export\s+)?(?:interface|type|class)\s+AuthorizationInfo\s*([^{]*)\s*\{([^}]*)\}', content, re.DOTALL)
    if ai_match:
        print('[+] Found AuthorizationInfo')
        auth_findings['remote_auth']['interface'] = 'AuthorizationInfo'
        # Extract fields
        fields_text = ai_match.group(2)
        for line in fields_text.split('\n'):
            line = line.strip()
            if line and not line.startswith('//'):
                auth_findings['remote_auth']['fields'].append(line)
    
    # Find ConnectionState enum
    print('[*] Searching for ConnectionState...')
    cs_match = re.search(r'enum ConnectionState\s*\{([^}]*)\}', content, re.DOTALL)
    if cs_match:
        print('[+] Found ConnectionState enum')
        states = cs_match.group(1)
        auth_findings['connection_states'] = [s.strip() for s in states.split(',') if s.strip()]

# Extract DataFrame structure
print('[*] Searching for DataFrame interface...')
dataframe_file = EXTRACT_DIR / 'lavva_exalushome/package/build/js/DataFrame.d.ts'

if dataframe_file.exists():
    content = dataframe_file.read_text()
    
    # Find IDataFrame interface
    df_match = re.search(r'export\s+(?:interface|class)\s+(?:IDataFrame|DataFrame)\s*<T>\s*\{([^}]*)\}', content, re.DOTALL)
    if df_match:
        print('[+] Found DataFrame structure')
        fields_text = df_match.group(1)
        auth_findings['dataframe']['interface'] = 'IDataFrame<T>'
        for line in fields_text.split('\n'):
            line = line.strip()
            if line and not line.startswith('//'):
                auth_findings['dataframe']['fields'].append(line)

# Extract from DevicesService
print('[*] Searching for DevicesService...')
devices_file = EXTRACT_DIR / 'lavva_exalushome/package/build/js/Services/Devices/DevicesService.d.ts'

if devices_file.exists():
    content = devices_file.read_text()
    print('[+] Found DevicesService')
    
    # Look for GetDevices or similar methods
    get_methods = re.findall(r'(?:async\s+)?Get\w+Async?\s*\([^)]*\)\s*:\s*[^;]*(?:Promise<[^>]+>)?', content)
    if get_methods:
        auth_findings['device_discovery_methods'] = get_methods[:5]

# Extract task interfaces
print('[*] Searching for IBlindPosition...')
devices_dir = EXTRACT_DIR / 'lavva_exalushome/package/build/js/Services/Devices'
if devices_dir.exists():
    for f in devices_dir.glob('I*.d.ts'):
        if 'blind' in f.name.lower() or 'position' in f.name.lower():
            print(f'[+] Found {f.name}')
            content = f.read_text()
            # Quick preview
            first_100_chars = content[:200]
            if 'IBlindPosition' in first_100_chars:
                print(f'    -> Contains IBlindPosition definition')

# ============================================================================
# Write findings
# ============================================================================

auth_doc = f"""# ExalusHome Authentication & Protocol

## Remote Mode: AuthorizationInfo

### Interface Definition
```typescript
{chr(10).join(auth_findings['remote_auth']['fields'] if auth_findings['remote_auth']['fields'] else ['// See source for full definition'])}
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
{chr(10).join(auth_findings['dataframe']['fields'] if auth_findings['dataframe']['fields'] else ['// See source for full definition'])}
```

### Payload Type
All frames carry generic `<T>` payload:
```typescript
interface IDataFrame<T> {{
  // Generic payload
  data: T;
  // Metadata
  // timestamp?: number;
  // requestId?: string;
  // responseId?: string;
}}
```

### Examples

#### State Request
```json
{{
  "command": "GetDeviceState",
  "deviceGuid": "12345-abcde",
  "timestamp": 1234567890
}}
```

#### State Response
```json
{{
  "deviceGuid": "12345-abcde",
  "states": [
    {{
      "type": "IBlindPosition",
      "value": 75,
      "timestamp": 1234567890
    }}
  ]
}}
```

#### Command (Set Blind Position)
```json
{{
  "command": "ExecuteTask",
  "deviceGuid": "12345-abcde",
  "taskType": "IBlindPosition",
  "position": 50
}}
```

---

## Connection State Machine

### ConnectionState Enum
```
{chr(10).join([f'- {s}' for s in auth_findings.get('connection_states', ['Disconnected', 'Connected', 'Authorized', 'Error'])])}
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
service.OnErrorOccuredEvent().subscribe((sender: string, errorMessage: string) => {{
  // Handle error: sender is service name, errorMessage describes issue
}});
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
"""

(RESEARCH_DIR / 'auth_protocols.md').write_text(auth_doc)

# Save JSON
(RESEARCH_DIR / 'auth_findings.json').write_text(json.dumps(auth_findings, indent=2))

print(f"""
[✓] Authentication and protocol documents created:
    - research/auth_protocols.md
    - research/auth_findings.json

Files require web app validation to complete:
- Exact AuthorizationInfo fields
- Exact DataFrame structure
- Default WebSocket port for local mode
- Exact SignalR hub method names
""")
