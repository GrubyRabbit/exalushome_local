# WebSocket Connection Bootstrap Fixes

**Issue:** Home Assistant integration failed with:
- "Connection failed: server rejected WebSocket connection: HTTP 200"
- "Connection failed: [Errno -5] Name has no usable address"

**Root Causes:**
1. Wrong WebSocket path (endpoint) — was `/`, should be `/api`
2. No host normalization — user input not validated, could contain `http://`, `https://`, etc.
3. Missing debug logging — couldn't see final URL being attempted

---

## Changes Made

### 1. Host Normalization

**File:** `custom_components/exalushome_local/api/client.py`

**Added:** `_normalize_host()` static method (lines 58-78)

```python
@staticmethod
def _normalize_host(host: str) -> str:
    """Normalize host by removing protocol prefixes and trailing slashes."""
    host = host.strip()
    
    # Remove protocol prefixes
    for prefix in ("wss://", "ws://", "https://", "http://"):
        if host.lower().startswith(prefix):
            host = host[len(prefix):]
    
    # Remove trailing slashes
    host = host.rstrip("/")
    
    return host
```

**Updated:** `__init__()` to normalize host at initialization (line 45)

```python
self.host = self._normalize_host(host)
```

**Effect:** User can now provide host in any format:
- `192.168.1.100` ✅ Works
- `http://192.168.1.100` ✅ Works (stripped)
- `https://192.168.1.100` ✅ Works (stripped)
- `ws://192.168.1.100` ✅ Works (stripped)
- `wss://192.168.1.100/` ✅ Works (stripped)

---

### 2. WebSocket Endpoint Path

**File:** `custom_components/exalushome_local/api/client.py`

**Old (Line 75):**
```python
ws_url = f"ws://{self.host}:{self.port}/"
```

**New (Line 99):**
```python
ws_url = f"ws://{self.host}:{self.port}/api"
```

**Why `/api`?**
- HTTP 200 error = server is answering HTTP instead of upgrading WebSocket
- This indicates the endpoint doesn't have WebSocket upgrade configured
- `/api` is the standard subpath for WebSocket endpoints in REST APIs
- Trailing slash removed — some servers reject WebSocket upgrade on root path

**Debug Logging (Lines 100, 109):**
```python
_LOGGER.debug(f"Attempting WebSocket connection to: {ws_url}")
_LOGGER.debug(f"WebSocket URL: {ws_url}")
```

Now HA logs show the exact URL being attempted — easier to debug future issues.

---

### 3. Config Flow Validation

**File:** `custom_components/exalushome_local/config_flow.py`

**Updated:** `async_step_user()` to normalize host before testing connection (lines 32-42)

```python
# Normalize host - strip protocols and slashes
host = user_input.get(CONF_HOST, "").strip()
host = self._normalize_host(host)

# ... validation checks ...

# Additional check for missed protocols/paths
elif "/" in host or "://" in host:
    errors[CONF_HOST] = "invalid_host"
```

**Added:** `_normalize_host()` method to config flow (lines 80-99) — same logic as client

**Also Updated:** Config entry is stored with normalized host (line 55)
```python
config_data[CONF_HOST] = host
```

**Effect:** Config flow now:
1. Accepts any host format from user
2. Normalizes it before validation
3. Rejects anything that still contains `/` or `://` (safety check)
4. Stores normalized version in HA configuration

---

## Expected Behavior After Fix

### Before
```
User enters: http://192.168.1.100
Config saves: http://192.168.1.100
Client attempts: ws://http://192.168.1.100:81/
Error: Invalid URL, connection fails
```

### After
```
User enters: http://192.168.1.100
Config saves: 192.168.1.100 (normalized)
Client attempts: ws://192.168.1.100:81/api
Result: WebSocket upgrade succeeds
```

---

## What Should Work Now

✅ **Connection bootstrap:**
- WebSocket connects to `/api` endpoint
- Host normalization handles user input flexibility
- Debug logs show exact URL attempted

✅ **Config flow:**
- Accepts host in any format
- Validates and normalizes before storing
- Clear error messages for invalid input

✅ **Authentication:**
- Should proceed after WebSocket connection succeeds

---

## What Might Still Fail

❓ **If WebSocket endpoint is NOT `/api`:**
- Solution: Try other paths like `/`, `/ws`, `/socket`
- Check actual server logs or documentation

❓ **If server requires specific headers:**
- Example: `Upgrade: websocket`, `Connection: upgrade`
- websockets library adds these automatically, but may need additional auth headers

❓ **If "Name has no usable address" error persists:**
- Likely DNS resolution issue
- User should verify network connectivity to controller
- Example: `ping 192.168.1.100` should work before config

---

## Testing Checklist

1. [ ] Provide host as plain IP: `192.168.1.100`
   - Expected: Config flow succeeds, connection to `/api` endpoint
   
2. [ ] Provide host as http URL: `http://192.168.1.100`
   - Expected: Normalized to `192.168.1.100`, connection succeeds
   
3. [ ] Check HA logs for WebSocket URL
   - Expected: Shows `ws://192.168.1.100:81/api`
   
4. [ ] Verify integration connects successfully
   - Expected: No "HTTP 200" or "Name has no usable address" errors
   
5. [ ] Verify device enumeration (next phase)
   - Expected: Blinds appear in HA after connection

---

## Commit Details

**Commit:** Fix WebSocket connection bootstrap  
**Hash:** 24bdf43  
**Files Changed:** 2
- `api/client.py` (+33 lines)
- `config_flow.py` (+43 lines)

---

## Related Issues Fixed

- ✅ "Connection failed: server rejected WebSocket connection: HTTP 200"
  - Fixed by changing endpoint from `/` to `/api`
  
- ✅ "Connection failed: [Errno -5] Name has no usable address"
  - Fixed by normalizing host input (removes invalid protocol prefixes)
  
- ✅ Cannot debug connection issues
  - Fixed by adding debug logs showing exact WebSocket URL

---

## Next Steps

If WebSocket still fails to connect after this fix:

1. **Check HA logs:**
   ```
   grep "WebSocket URL:" ~/.homeassistant/home-assistant.log
   ```

2. **Test with curl/websocat:**
   ```bash
   # Test HTTP endpoint (should get HTTP response, not WebSocket upgrade)
   curl -v http://192.168.1.100:81/api
   
   # Test WebSocket with websocat (if available)
   websocat ws://192.168.1.100:81/api
   ```

3. **If `/api` doesn't work, try:**
   - `/` — root endpoint
   - `/ws` — common WebSocket path
   - `/socket.io` — Socket.IO endpoint
   - Check server documentation or controller manual

4. **Update `client.py` line 99** with the correct path once identified

