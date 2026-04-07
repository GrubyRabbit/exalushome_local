# Changelog

All notable changes to ExalusHome Local Home Assistant integration will be documented in this file.

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

## Protocol Details (v0.0.2)

**Local Connection:**
- WebSocket: `ws://controller_ip:81/api`
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
- Shutter identification: "IBlindPosition" in AvailableTasks

---

## Known Limitations

- Local mode only (no cloud/remote mode)
- No support for other device types (cameras, intercoms, etc.)
- Blinds only (ControlFeature=3)
- Requires controller IP, serial, and PIN in HA configuration
- WebSocket endpoint path assumed to be `/api` (may vary by controller)

## Next Steps

- [ ] Test against real ExalusHome controller
- [ ] Verify device enumeration works
- [ ] Validate state event reception
- [ ] Test command execution (open/close/stop/position)
- [ ] Add configuration options (refresh rate, device name customization)
- [ ] Support for multiple controllers
