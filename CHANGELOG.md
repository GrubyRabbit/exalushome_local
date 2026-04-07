# Changelog

All notable changes to ExalusHome Local Home Assistant integration will be documented in this file.

## [v0.0.4] - 2026-04-07

### Fixed
- 2-step configuration flow: collect controller info (host, serial, pin) then user credentials (email, password)
- Session login now uses real user email and password from config flow (not hardcoded placeholders)
- Coordinator and platform properly thread email/password through to WebSocket client
- Config entry data now stored with all five credential fields

### Added
- CONF_EMAIL and CONF_PASSWORD configuration constants
- 2-step async_step_user → async_step_user_credentials flow in config_flow.py
- Email/password parameters to ExalusHomeLocalCoordinator.__init__
- Email/password extraction in cover.py async_setup_entry
- Proper credential threading through __init__.py hass.data storage

### Changed
- Config flow: Step 1 collects controller connection info, Step 2 collects user credentials
- ExalusLocalClient now receives email and password as constructor parameters
- _create_session() uses self.email and self.password instead of hardcoded values
- Config validation tests connect() with real user credentials before saving

### Technical
- HTTP GET /controller_info: validates controller PIN (step 1 independent)
- WebSocket session login: uses real user email + password from step 2
- /devices/list now called only after successful session creation
- All auth/session debug logs include status values

## [v0.0.3] - 2026-04-07

### Fixed
- Local authentication flow: replaced WebSocket /system/authorize with HTTP GET /controller_info validation
- Session login prerequisite: added /users/user/login WebSocket request before device enumeration
- Device enumeration: check response.Status before parsing Data (fixes Data=null crashes)
- Error handling: Status values now logged (e.g., Status=13 UserNotLoggedIn) instead of silent failures

### Added
- HTTP controller_info validation (LocalNetworkExalusConnectionService.js:195-226 pattern)
- Session login request via /users/user/login (LocalNetworkExalusConnectionService.js:264 prerequisite)
- Protocol Status constants (OK=0, UserNotLoggedIn=13, etc.)
- Debug logging for auth, session, and device enumeration steps

### Changed
- connect() flow: HTTP auth → WebSocket connect → Session login (waits for all 3 steps)
- fetch_devices() now validates session is established before sending /devices/list
- Response parsing validates Status == OK before accessing Data field

## [v0.0.2] - 2026-04-07

### Added
- WebSocket client for local ExalusHome controller connection (port 81)
- Device enumeration via `/devices/list` endpoint
- Blind/shutter position state tracking with inverted HA position mapping
- Cover entity support with open/close/stop/set_position commands
- Real-time state updates via WebSocket push events

### Fixed
- WebSocket connection bootstrap: normalize host input (strip http://, https://, ws://, wss://)
- WebSocket endpoint path: use `/api` instead of root path (fixes HTTP 200 error)
- Host validation in config flow to prevent malformed URLs
- Device enumeration response parsing

### Improved
- HACS compatibility with proper manifest configuration
- Debug logging for WebSocket connection troubleshooting
- Configuration flow validation and error messages
- Protocol constants clearly isolated in codebase

### Changed
- Position mapping: Exalus 0=open/100=closed → HA 100=open/0=closed (correct inversion)
- ControlFeature hardcoded to 3 for blind devices
- Entity unique ID uses DeviceGuid + Channel

## [v0.0.1] - Initial Release (not published)

### Initial
- Project skeleton created
- Research and validation infrastructure
- Base integration structure

---

## Protocol Details (v0.0.4)

**Local Connection (Fixed in v0.0.3, Credentials in v0.0.4):**
- HTTP validation: GET `http://controller_ip/controller_info` → verify response == "serial:pin"
- WebSocket: `ws://controller_ip:81/api`
- Session login: PUT `/users/user/login` (required before /devices/list)
  - Uses real user email and password from Home Assistant config flow
- Device enumeration: GET `/devices/list` (after session established)
- No cloud dependency
- Event-driven updates (no polling)

**Commands:**
- Open: Data=101
- Close: Data=102
- Stop: Data=103
- Set Position: Data=0-100 (Exalus scale)

**State:**
- Resource: `/info/devices/device/state/changed`
- DataType: BlindPosition
- Position: 0-100 scale (0=open, 100=closed in Exalus)

**Device Enumeration:**
- Resource: `/devices/list`
- Method: GET (0)
- Prerequisite: Session must be logged in via /users/user/login
- Shutter identification: "IBlindPosition" in AvailableTasks

---

## Known Limitations

- Local mode only (no cloud/remote mode)
- No support for other device types (cameras, intercoms, etc.)
- Blinds only (ControlFeature=3)
- Requires controller IP, serial, PIN, user email, and password in HA configuration

## Next Steps

- [ ] Test against real ExalusHome controller with real user credentials
- [ ] Verify device enumeration works with Step 2 credentials
- [ ] Validate state event reception
- [ ] Test command execution (open/close/stop/position)
- [ ] Add configuration options (refresh rate, device name customization)
- [ ] Support for multiple controllers
