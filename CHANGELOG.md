# Changelog

## 1.0.4

- Fixed duplicated entity names for cover and microventilation button entities
- Added proper Home Assistant device/entity naming
- No changes to command logic or websocket handling

## 1.0.3

- Added producer-confirmed microventilation button support
- Uses captured Exalus WebApp payload: ControlFeature=13, Data=91
- Adds shared coordinator setup for cover/button platforms
- Adds README note about delayed position/state updates following Exalus WebApp behavior

## 1.0.2

- Fixed Home Assistant Logbook spam caused by stale cover command state
- No functional changes to movement detection
- Producer-aligned internal fix

## 1.0.1

- Producer-aligned session recovery
- Status=13 UserIsNotLoggedIn detection and handling
- Automatic session restoration with stored credentials
- Retry failed commands once after successful recovery
- Command response handling aligned with producer behavior (15s timeout)
- Prevents concurrent recovery attempts

## 1.0.0

- First Stable release
- Full alignment with Exalus webapp behavior (1:1)
- Removed experimental and custom logic
- Documentation simplified

---

## Known Limitations

- Local mode only (no cloud/remote mode)
- No support for other device types (cameras, intercoms, etc.)
- Blinds only (ControlFeature=3)
- Requires controller IP, serial, PIN, user email, and password in HA configuration
