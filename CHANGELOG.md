# Changelog

All notable changes to ExalusHome Local Home Assistant integration will be documented in this file.

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

## Protocol Details (v0.0.3)

**Local Connection (Fixed in v0.0.3):**
- HTTP validation: GET `http://controller_ip/controller_info` → verify response == "serial:pin"
- WebSocket: `ws://controller_ip:81/api`
- Session login: PUT `/users/user/login` (required before /devices/list)
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
- Requires controller IP, serial, and PIN in HA configuration
- /users/user/login credentials: currently hardcoded to local placeholder (Email: "local@exalushome.local")

## Next Steps

- [ ] Test against real ExalusHome controller
- [ ] Verify device enumeration works
- [ ] Validate state event reception
- [ ] Test command execution (open/close/stop/position)
- [ ] Investigate if /users/user/login requires different credentials
- [ ] Add configuration options (refresh rate, device name customization)
- [ ] Support for multiple controllers
