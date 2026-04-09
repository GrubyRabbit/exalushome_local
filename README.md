# ExalusHome Local — Home Assistant Integration

Local network integration for **Exalus** smart home controllers.  
Controls roller shutters (blinds) directly over LAN — no cloud required.

> **State and movement reflect the official Exalus web application 1:1**

---

## What it supports

- Local control of Exalus roller shutters (blinds)
- Open / close / stop / set position
- Live position updates from the controller
- Live movement state (opening / closing / stopped)
- Automatic reconnect on session loss

---

## Installation

### HACS (recommended)

1. Add this repository as a custom repository in HACS:  
   `https://github.com/GrubyRabbit/hatest`  
   Category: **Integration**
2. Install **ExalusHome Local**
3. Restart Home Assistant

### Manual

1. Copy `custom_components/exalushome_local/` into your HA `custom_components/` directory
2. Restart Home Assistant

---

## Configuration

1. Go to **Settings → Devices & Services → Add Integration**
2. Search for **ExalusHome Local**
3. Enter:
   - Controller IP address
   - Serial number
   - PIN
   - Account email and password

---

## Notes

- Requires the Exalus controller to be reachable on the local network
- Behavior depends on the Exalus local API — no artificial state simulation
- Only roller shutter (blind) channels are exposed as cover entities

