# Home Assistant Integration Specification: ExalusHome

## Executive Summary

This document specifies the design for a Home Assistant custom integration supporting ExalusHome roller shutters/blinds.
The integration supports two independent connection modes (remote/cloud and local/direct IP) with intelligent fallback behavior.

---

## 1. Integration Metadata

### Domain
```
exalushome
```

### Naming Convention
- **Integration:** ExalusHome
- **Devices:** ExalusHome Shutters
- **Service:** exalushome.set_blind_position
- **Climate entity:** climate.exalushome_*

### Supported Platforms
- `cover` (primary) — for blinds/shutters
- Potentially: `sensor`, `climate`, `switch` (future)

### Features
- ✅ Discover shutters
- ✅ Read current position
- ✅ Read availability
- ✅ Open / Close / Stop commands
- ✅ Set exact position (if device supports)
- ✅ Dual connection modes (remote/local)
- ✅ Automatic fallback (local → remote if configured)
- ✅ Multi-device support
- ✅ Multi-controller support (future: load-balance)

---

## 2. Connection Modes

### Mode: Remote / Cloud

**Config Entry Option:** `connection_mode: "remote"`

**Requirements:**
- ExalusHome account / credentials
- Internet connectivity
- Access to cloud broker (exalushome.tr7.pl)

**Fields:**
- Username / Email
- Password
- Controller Serial Number
- Controller PIN

**Pros:**
- Access from anywhere
- Multi-user support
- Automatic failover via cloud broker

**Cons:**
- Internet required
- Higher latency
- Cloud dependency

**Discovery:**
- Device enumeration via cloud API
- Automatic controller discovery (user selects from list)

### Mode: Local / Direct IP

**Config Entry Option:** `connection_mode: "local"`

**Requirements:**
- Local network access to controller
- Controller IP address and port
- Controller Serial Number
- Controller PIN

**Fields:**
- Controller IP Address
- Port (default 81)
- Serial Number
- PIN

**Pros:**
- No internet required
- Lower latency (LAN-only)
- Local-only network isolation
- Faster response times

**Cons:**
- Must be on same local network
- Manual configuration (no central device registry)
- No multi-user support
- No automatic failover

**Discovery:**
- Manual IP entry (most straightforward)
- Future: mDNS discovery
- Future: Network port scanning

### Mode: Dual / Fallback

**Config Entry Option:** `connection_mode: "dual"`

**Behavior:**
1. Connect to local controller first
2. If local connection fails → fall back to remote
3. If both fail → integration unavailable
4. Prefer local when both available (lower latency)

**Configuration:**
```yaml
exalushome:
  connection_mode: dual
  # Remote credentials (fallback)
  remote:
    username: user@example.com
    password: password
    serial_number: ABC123
    pin: "0000"
  # Local connection (primary)
  local:
    host: 192.168.1.100
    port: 81
    serial_number: ABC123
    pin: "0000"
```

---

## 3. Configuration Flow

### Initial Setup (via Integrations UI)

**Step 1: Connection Mode Selection**
```
Radio buttons:
  ○ Remote / Cloud
  ○ Local / LAN Only
  ○ Dual (local primary, remote fallback)
```

**Step 2a: Remote Mode**
```
Form Fields:
  - Email / Username [text input]
  - Password [password input]
  - Controller Serial Number [text input] or [dropdown of discovered]
  - Controller PIN [password input, default "0000"]
  
Button: Discover Controllers (auto-populate serial number dropdown)
Button: Next / Create Integration
```

**Step 2b: Local Mode**
```
Form Fields:
  - Controller IP Address [text input, default from mDNS if available]
  - Port [number input, default 81]
  - Controller Serial Number [text input or dropdown]
  - Controller PIN [password input]
  
Button: Test Connection
Button: Discover Devices
Button: Create Integration
```

**Step 2c: Dual Mode**
```
Form Fields (Remote):
  - Email / Username [text input]
  - Password [password input]
  - Serial Number [text dropdown with discovery]
  - PIN [password input]

Form Fields (Local):
  - IP Address [text input]
  - Port [number input, default 81]
  - Serial Number [prefilled from remote if same]
  - PIN [prefilled from remote if same]

Button: Test Remote Connection
Button: Test Local Connection
Button: Create Integration
```

**Step 3: Device Selection (Optional)**
```
Checkbox List:
  ☑ Blind: Living Room
  ☑ Blind: Bedroom 1
  ☑ Blind: Bedroom 2
  ☐ Light: Ceiling Lamp (not blinds, hide)
  
Button: Create Integration (auto-discover later)
```

**Step 4: Name Configuration**
```
Text Input: Integration Name [default "ExalusHome"]
Drop-down: Area Assignment [Living Room, Bedroom, ...]
```

---

## 4. Re-authentication

### When Triggered
- Pin/serial number invalid
- Cloud credentials expired
- User initiates reauthentication

### Reauth Flow
```
Option 1: Modify Integration Settings (in-UI)
  Settings → Integrations → ExalusHome → Options
  
Option 2: Delete and Reconfigure
  Settings → Integrations → ExalusHome → Delete
  Then: Create New Integration
  
Option 3: Inline Reauth (HA 2022.8+)
  If connection fails, show "Reauth" button in notification
  Click → Config flow restarts
```

### Reauth Form
```
Same as initial setup, but:
- Pre-filled with existing values (if valid)
- Option to change connection mode
- Option to switch from remote ↔ local ↔ dual
```

---

## 5. Data Flow Architecture

### Startup Sequence
```
1. Load integration configuration from home-assistant/config/config_entries
2. Instantiate ConnectionMode strategy (Remote/Local/Dual)
3. Attempt connection (with retries/backoff)
4. On connection success:
   a. Instantiate DevicesCoordinator
   b. Fetch device list and initial state
   c. Create CoverEntity for each blind
   d. Set up state polling / subscription
5. Expose entities to HA
6. Ready for commands
```

### Coordinator Pattern

```python
class ExalusHomeCoordinator(DataUpdateCoordinator):
    """Fetch data from ExalusHome and manage updates."""
    
    async def _async_update_data(self):
        """Poll devices for updated state."""
        try:
            devices = await self.connection.get_devices()
            for device in devices:
                states = await self.connection.get_device_state(device.guid)
                self.data[device.guid] = states
            return self.data
        except ExalusAuthError:
            # Trigger reauth
            raise ConfigEntryAuthFailed
        except ExalusConnectionError:
            # Retry later
            raise UpdateFailed
```

### Update Interval
```
Default: 30 seconds (polling)
Future: Support push updates via WebSocket subscription (on demand)
Configurable: Via service call
```

### Connection Management

```python
class ExalusConnectionStrategy(ABC):
    """Abstract base for Remote/Local/Dual modes."""
    
    @abstractmethod
    async def connect(self, config: ConfigEntry):
        pass
    
    @abstractmethod
    async def disconnect(self):
        pass
    
    @abstractmethod
    async def get_devices(self) -> List[Device]:
        pass
    
    @abstractmethod
    async def get_device_state(self, device_guid: str) -> DeviceState:
        pass
    
    @abstractmethod
    async def set_blind_position(self, device_guid: str, position: int):
        pass

class RemoteConnection(ExalusConnectionStrategy):
    """Cloud-based connection via SignalR."""
    
class LocalConnection(ExalusConnectionStrategy):
    """LAN-only WebSocket connection."""

class DualConnection(ExalusConnectionStrategy):
    """Try local first, fall back to remote."""
```

---

## 6. CoverEntity Implementation

### Mapping from ExalusHome to HA Cover

```python
class ExalusHomeCover(CoverEntity):
    """Representation of an ExalusHome blind/shutter."""
    
    # HA Required Properties
    @property
    def name(self) -> str:
        """Return friendly name."""
        return self.device.name  # "Living Room Blind"
    
    @property
    def unique_id(self) -> str:
        """Return unique identifier."""
        return f"exalushome_{self.device.guid}"
    
    @property
    def device_info(self) -> DeviceInfo:
        """Return device info for HA grouping."""
        return DeviceInfo(
            identifiers={(DOMAIN, self.device.guid)},
            manufacturer="ZAMEL",
            model=self.device.model,
            name=self.device.name,
            fw_version=self.device.firmware_version,
            hw_version=self.device.serial_number,
        )
    
    # HA Position Properties
    @property
    def current_cover_position(self) -> int | None:
        """Return position 0-100 (0=open, 100=closed)."""
        # Convert ExalusHome position to HA convention
        # NOTE: May need to invert depending on device orientation
        state = self._get_blind_position_state()
        return state.position if state else None
    
    @property
    def is_opening(self) -> bool:
        """Return True if cover is opening."""
        return self.device.movement_state == MovementState.Opening
    
    @property
    def is_closing(self) -> bool:
        """Return True if cover is closing."""
        return self.device.movement_state == MovementState.Closing
    
    @property
    def available(self) -> bool:
        """Return True if device is available."""
        return self.device.state == DeviceState.Working
    
    # HA Supported Features
    @property
    def supported_features(self) -> CoverEntityFeature:
        """Return supported features."""
        features = (
            CoverEntityFeature.OPEN |
            CoverEntityFeature.CLOSE |
            CoverEntityFeature.STOP
        )
        if self.device.supports_set_position:
            features |= CoverEntityFeature.SET_POSITION
        return features
    
    # HA Actions
    async def async_open_cover(self, **kwargs):
        """Open the cover (set to 0 position)."""
        await self.coordinator.connection.set_blind_position(
            self.device.guid, 
            position=0  # or 100? Depends on orientation
        )
    
    async def async_close_cover(self, **kwargs):
        """Close the cover (set to 100 position)."""
        await self.coordinator.connection.set_blind_position(
            self.device.guid,
            position=100  # or 0?
        )
    
    async def async_stop_cover(self, **kwargs):
        """Stop the cover if currently moving."""
        await self.coordinator.connection.stop_blind(self.device.guid)
    
    async def async_set_cover_position(self, **kwargs):
        """Set cover to specific position."""
        position = kwargs[ATTR_POSITION]  # 0-100
        await self.coordinator.connection.set_blind_position(
            self.device.guid,
            position=position
        )
```

### Key Mappings

| ExalusHome | Home Assistant | Notes |
|-----------|-----------------|-------|
| Device GUID | unique_id | Ensures persistence across reboots |
| Device Name | friendly_name | "Living Room Blind" |
| Device State | available | Working=on, NotResponding=off |
| Position | current_cover_position | May need inversion (0=open vs closed) |
| Movement State | is_opening/is_closing | From task execution state |
| SetBlindPosition | async_set_cover_position | If supported |
| Roles.Blind | CoverEntity | Filter for blind-type devices |

---

## 7. Services

### Standard HA Cover Services
All standard services apply:
- `cover.open_cover`
- `cover.close_cover`
- `cover.stop_cover`
- `cover.set_cover_position`
- `cover.toggle`

### Custom Services (Optional)

```yaml
# Custom position setting with specific direction
exalushome.set_blind_microventilation:
  description: "Enable ventilation mode (tilt blinds)"
  target:
    entity:
      domain: cover
      integration: exalushome
  fields:
    angle:
      description: "Microventilation angle (0-90 degrees)"
      selector:
        number:
          min: 0
          max: 90
          step: 5

# Recalibrate blind timing
exalushome.calibrate_blind:
  description: "Recalibrate blind open/close timing"
  target:
    entity:
      domain: cover
      integration: exalushome
```

---

## 8. Diagnostics

### Exposed Diagnostics (Redacted)

```python
async def async_get_diagnostics(self, config_entry: ConfigEntry):
    """Return diagnostics data."""
    return {
        "connection_mode": config_entry.data.get("connection_mode"),
        "devices_count": len(self.coordinator.data),
        "devices": [
            {
                "guid": device.guid,  # OK to expose
                "name": device.name,  # OK to expose
                "type": device.icon_type,  # OK to expose
                "state": device.state.name,  # OK to expose
                "position": device.get_blind_position(),  # OK to expose
                # DO NOT EXPOSE:
                # "pin": device.pin,  # SECRET
                # "serial": device.serial,  # SENSITIVE
            }
            for device in self.coordinator.data.values()
        ],
        "connection_info": {
            "mode": "remote" or "local",  # OK
            "uptime_seconds": self.uptime,  # OK
            "last_update": self.last_update,  # OK
            # DO NOT EXPOSE:
            # "username": ...,  # SECRET
            # "password": ...,  # SECRET
            # "ip_address": ...,  # SENSITIVE (but may be OK if user adds)
        }
    }
```

### Redaction Rules

**Never expose:**
- Passwords, PINs, auth tokens
- API keys, secrets
- Email addresses (maybe OK in diagnostics if user logged in)
- Full IP addresses if on public internet (maybe OK for local-only)

**OK to expose:**
- Device names and guids
- Device types and models
- Current position and state
- Connection mode (remote/local)
- Firmware versions
- Integration version

---

## 9. Logging Strategy

### Log Levels

```python
# DEBUG: Frame-by-frame protocol details
_LOGGER.debug(f"Sending frame: {frame}")
_LOGGER.debug(f"Received frame: {frame}")

# INFO: Connection events
_LOGGER.info("Connected to ExalusHome remote broker")
_LOGGER.info("Authorizing controller ABC123")
_LOGGER.info("Discovered 5 blind devices")

# WARNING: Degradation
_LOGGER.warning("Local connection failed, falling back to remote")
_LOGGER.warning("Device ABC123 not responding (offline?)")
_LOGGER.warning("Re-authentication required")

# ERROR: Failures
_LOGGER.error("Failed to connect to broker: timeout")
_LOGGER.error("Authorization failed: invalid PIN")
_LOGGER.error(f"Unexpected error: {exc}", exc_info=True)
```

### Sensitive Data Handling

```python
# NEVER log passwords, PINs, tokens
_LOGGER.debug(f"Auth info: serial={serial}, pin=****")

# OK to log IP addresses (if local-only or user-provided)
_LOGGER.info(f"Connecting to local controller: {ip}:{port}")

# OK to log device guids, names, positions
_LOGGER.info(f"Device {device.name} position: {position}%")
```

---

## 10. Error Handling Strategy

### Connection Errors

```
AuthorizationError → ConfigEntryAuthFailed → User reauth required
ConnectionError → UpdateFailed → Retry on next poll
TimeoutError → UpdateFailed → Exponential backoff
InvalidPINError → ConfigEntryAuthFailed → Reauth required
```

### Recovery Strategies

#### Automatic Recovery
- Connection loss → Retry with exponential backoff
- Transient timeout → Retry next poll cycle
- Device offline → Mark unavailable, keep retrying

#### Manual Recovery
- Invalid credentials → Show reauth button in notification
- Connection mode mismatch → Delete and reconfigure
- Controller moved → Update IP address in options

### User Notifications

```python
# Show persistent notification for critical errors
async def _notify_error(self, title: str, message: str):
    self.hass.components.persistent_notification.create(
        message=message,
        title=title,
        notification_id=f"exalushome_{self.entry.entry_id}",
    )
```

Examples:
- "ExalusHome: Connection Lost" (auto-recovers)
- "ExalusHome: Re-authentication Required" (with reauth button)
- "ExalusHome: Local Controller Not Found" (suggest IP change)

---

## 11. Multi-Device & Multi-Controller (Future)

### Single Integration, Multiple Controllers
```yaml
exalushome:
  - name: "Primary Home"
    connection_mode: dual
    # ...
    
  - name: "Vacation House"
    connection_mode: remote
    # ...
```

**Implementation:** Multiple config entries, each with own coordinator.

### Load Balancing / Health Checks
```
If multiple controllers on same network:
- Ping all controllers on startup
- Use lowest-latency controller for subsequent commands
- Failover to alternate if primary becomes unavailable
```

---

## 12. Configuration & Data Storage

### Entry Data Structure
```python
{
    "title": "ExalusHome - Remote",
    "domain": "exalushome",
    "version": 1,
    "data": {
        "connection_mode": "remote" | "local" | "dual",
        "remote": {
            "username": "user@example.com",  # Encrypted in storage
            "password": "***",               # Encrypted
            "serial_number": "ABC123",
            "pin": "0000",                   # Encrypted
        },
        "local": {
            "host": "192.168.1.100",
            "port": 81,
            "serial_number": "ABC123",
            "pin": "0000",  # Encrypted
        },
    },
    "options": {
        "update_interval": 30,  # seconds
        "include_unavailable": False,
        # Future options:
        # "position_invert": False,
        # "enable_tilt": True,
        # "multidata_support": "auto",
    },
}
```

### Encrypted Storage
Use `async_validate_input()` and HA's built-in encryption for sensitive fields:
```python
# Handled by HA automatically for config entries
```

---

## 13. Testing Strategy

### Unit Tests
- DataFrame serialization/deserialization
- Position scale conversions
- Error code mappings

### Integration Tests
- Config flow with mock connection
- Entity creation and updates
- Command execution

### Real-World Tests (Manual)
- Remote connection (requires account)
- Local connection (requires controller on LAN)
- Dual fallback behavior
- State synchronization
- Command execution and feedback

---

## 14. Implementation Roadmap

### Phase 1: MVP (Initial Release)
- ✅ Remote connection mode
- ✅ Local connection mode (basic)
- ✅ CoverEntity with open/close/set-position
- ✅ Device discovery
- ✅ State polling
- ✅ Basic error handling

### Phase 2: Improvements
- ⏳ Dual mode with fallback
- ⏳ Push-based updates (WebSocket subscription)
- ⏳ Microventilation (tilt) support
- ⏳ Climate entity (temperature control)

### Phase 3: Advanced
- ⏳ mDNS controller discovery
- ⏳ Multi-controller support
- ⏳ Automations and scenes
- ⏳ Smart learning (timing calibration)

---

## 15. Known Unknowns & Validation Needed

### Critical Questions
1. **Position Scale:** What are actual min/max values from devices?
   - Solution: Sniff web app API, test with real controller
2. **Stop Command:** How to stop blind mid-movement?
   - Solution: Check if SetBlindPositionSimple or dedicated stop task
3. **Controller Discovery:** How does official app find controllers on LAN?
   - Solution: Network analysis (mDNS? broadcast? manual entry?)
4. **Multi-Channel:** How are multi-channel devices represented?
   - Solution: Analyze DeviceChannel handling
5. **Availability:** What indicates device is online/offline/broken?
   - Solution: Confirm DeviceState enum usage

### Validation Plan
1. **Phase 1 (Code Review):** Analyze remaining npm package files
2. **Phase 2 (Web App Sniffing):** Intercept real API calls from https://exalushome.tr7.pl/
3. **Phase 3 (Real Hardware):** Test with actual controller if available
4. **Phase 4 (Community):** Get feedback from ExalusHome users

---

## Appendix A: File Structure

```
custom_components/exalushome/
├── __init__.py                 # Integration setup
├── const.py                    # Constants, domains
├── config_flow.py              # Configuration UI
├── coordinator.py              # Data coordinator
├── manifest.json               # HA integration metadata
├── strings.json                # UI translations
├── cover.py                    # CoverEntity implementation
├── diagnostics.py              # Diagnostics support
├── api/
│   ├── __init__.py
│   ├── base.py                 # ConnectionStrategy ABC
│   ├── remote.py               # ExalusConnectionService wrapper
│   ├── local.py                # LocalNetworkExalusConnectionService wrapper
│   └── dual.py                 # Dual mode with fallback
├── models/
│   ├── __init__.py
│   ├── device.py               # Device data model
│   ├── state.py                # State data model
│   └── errors.py               # Custom exceptions
└── translations/
    ├── en.json
    └── (other languages)
```

---

## Appendix B: External Resources

- [ExalusHome Web App](https://exalushome.tr7.pl/)
- [npm Package: lavva.exalushome](https://www.npmjs.com/package/lavva.exalushome)
- [npm Package: lavva.exalushome.portos](https://www.npmjs.com/package/lavva.exalushome.portos)
- [Home Assistant: Custom Component Development](https://developers.home-assistant.io/docs/creating_component_index)
- [Home Assistant: CoverEntity](https://developers.home-assistant.io/docs/core/entity/cover/)
