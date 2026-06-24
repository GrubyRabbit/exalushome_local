# Changelog

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
