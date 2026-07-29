# ExalusHome Local — Home Assistant Integration

"Cała integracja napisana za pomocą agentów AI. Projekt powstał z powodu niedotrzymanych obietnic. Long story short - po paru latach czekania, zdecydowałem się zrobić to samemu, bo jak widać na moim przykładzie nie doczekali byśmy się sterowania tymi roletami w HA".

Local network integration for **Exalus** Tr7 433mhz smart home controllers.  
Controls roller shutters (blinds) directly over LAN — no cloud.

> **State and movement reflect the official Exalus web application 1:1**

---

## What it supports

- Local control of Exalus roller shutters (blinds)
- Open / close / stop / set position / microventilation
- Live position updates from the controller (this is not live as live you wish, exalus has limited information on this)
- Live movement state (opening / closing / stopped)
- Automatic reconnect on session loss

---

## Installation

### HACS (recommended)

1. Add this repository as a custom repository in HACS:  
   `https://github.com/GrubyRabbit/exalushome_local`  
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

## Tile cards

<img width="1044" height="1102" alt="tile cards with exalus shutters and microventilation" src="https://github.com/user-attachments/assets/a198c53d-227a-467b-9c81-d14bbead75e5" />

---

## Security

This integration never stores credentials in the repository.
If you discover a security issue, please open a private GitHub Security Advisory or contact me before publishing details.

---

## Notes

- Requires the Exalus controller Tr7 to be reachable on the local network (set static address IP)
- Behavior depends on the Exalus local API
- Only roller shutter (blind) channels are exposed as cover entities
- State and position updates follow Exalus local API/WebApp behavior. Reported position may update with delay after movement finishes. The integration does not simulate or guess final position.
