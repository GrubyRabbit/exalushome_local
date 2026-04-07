# ExalusHome Home Assistant Integration

**Status:** 🟢 Research Complete  
**Documentation:** 2,600+ lines of technical specification  
**npm Packages Analyzed:** 5 packages (complete)  
**Phases Complete:** 1-5, 8 (Research and HA spec)  
**Next:** Validation (phases 6-7), Implementation (phase 9)

---

## Quick Reference

### 📚 Technical Documentation

Core research documents (in `research/`):
- **package_map.md** — Architecture of 5 npm packages
- **transport_modes.md** — Remote (SignalR) vs Local (WebSocket port 81)
- **auth_remote.md** — Cloud authentication via AuthorizationInfo(serial, pin)
- **auth_local.md** — Local network auth, WebSocket to port 81
- **entities.md** — Device/Channel models
- **commands.md** — Shutter task types and execution
- **ha_integration_spec.md** — Complete HA integration design (21KB)

### 🎯 Key Findings

**Remote Mode (Cloud):**
```
Protocol: Microsoft SignalR
Broker: exalushome.tr7.pl (inferred)
Auth: AuthorizationInfo(serial_number, pin)
Transport: WebSocket via cloud broker
Keep-Alive: Ping/pong mechanism
```

**Local Mode (LAN):**
```
Protocol: Custom binary over WebSocket
Port: 81 (hardcoded)
Auth: Same AuthorizationInfo(serial_number, pin)
Transport: Direct to controller IP:81
Validation: http://controller_ip/controller_info → SERIAL:PIN
Keep-Alive: Ping every 5 seconds
```

**Shutter Commands:**
```
Primary: SetBlindPosition (interface: IBlindPosition)
  - Position scale: UNKNOWN (0-100%? 0-255? validate needed)
  - Stop mechanism: UNKNOWN (validate needed)

Secondary:
  - SetBlindPositionSimple (simplified control)
  - SetBlindMicroventilation (tilt/ventilation)
  - SetBlindOpenCloseTime (timing calibration)
```

### 📋 Critical Unknowns (Validation Required)

1. **Position Scale** — Is it 0-100%, 0-255, 0-180°, or custom?
2. **Stop Command** — How to stop blind mid-movement?
3. **Local Discovery** — How does app find controllers on LAN?
4. **State Updates** — Push via WebSocket or polling only?
5. **Multi-Channel** — How are devices with multiple blinds exposed?

See `IMPLEMENTATION_STARTER.md` for validation checklist and method.

---

## Project Structure

```
/
├── README.md                          ← You are here
├── STATUS_REPORT.md                   (Detailed completion report)
├── IMPLEMENTATION_STARTER.md          (Code starter + validation guide)
├── plan.md                            (Session planning)
├── research/                          (Technical documentation)
│   ├── package_map.md
│   ├── transport_modes.md
│   ├── auth_remote.md
│   ├── auth_local.md
│   ├── entities.md
│   ├── commands.md
│   ├── ha_integration_spec.md
│   └── *.json                         (Structured findings)
├── scripts/                           (Analysis tools)
│   ├── unpack_packages.py             (Extract npm packages)
│   ├── inspect_exports.py             (Analyze exports)
│   ├── document_findings.py           (Generate docs)
│   └── extract_protocols.py           (Protocol details)
└── artifacts/                         (Data files)
    ├── package_versions.json
    ├── exports_analysis.json
    └── (file listings)
```

---

## Getting Started

### Read the Research
1. Start with **STATUS_REPORT.md** (overview)
2. Read **IMPLEMENTATION_STARTER.md** (next steps)
3. Dive into `research/ha_integration_spec.md` (full design)
4. Review specific protocol docs as needed

### Validate Critical Items
See `IMPLEMENTATION_STARTER.md` section "Validation Checklist" for:
- How to sniff web app API calls
- What to look for in network captures
- Where to find position scale and stop command

### Start Implementation
Once validation complete:
1. Use `research/ha_integration_spec.md` as guide
2. Start with Python API abstraction (`api/base.py`)
3. Implement remote connection first (easier, no LAN needed)
4. Add local connection
5. Build HA custom component

---

## Key Insights

✅ **Confirmed:**
- Dual connection support (remote + local)
- Identical auth for both modes
- HTTP-like protocol with DataFrame containers
- Task-based command execution
- Device model with dynamic capabilities
- Keep-alive ping mechanisms
- Session restoration on network loss

⚠️ **Unknown (Requires Validation):**
- Position value scale and direction
- Stop command implementation
- Local device discovery mechanism
- Push vs polling for state updates

---

## Documentation Stats

| Document | Lines | Focus |
|----------|-------|-------|
| STATUS_REPORT.md | 290 | Research completion summary |
| IMPLEMENTATION_STARTER.md | 372 | Validation checklist + code starter |
| research/ha_integration_spec.md | 779 | Complete HA integration design |
| research/auth_remote.md | 392 | Cloud auth protocol |
| research/auth_local.md | 300 | Local auth protocol |
| research/commands.md | 315 | Shutter commands |
| research/entities.md | 162 | Device models |
| research/package_map.md | 129 | Package architecture |
| research/transport_modes.md | 191 | Protocol comparison |

**Total:** 2,930 lines of technical documentation

---

## Progress Tracking

**Research Phase (Complete):**
- ✅ Phase 1: Package Acquisition (5 npm packages extracted)
- ✅ Phase 2: Source Analysis (Exports and keywords identified)
- ✅ Phase 3: Remote Mode Mapping (SignalR documented)
- ✅ Phase 4: Local Mode Mapping (WebSocket on port 81 documented)
- ✅ Phase 5: Entity Analysis (Device models and commands)
- ✅ Phase 8: HA Spec (Complete integration design)

**Validation Phase (In Progress):**
- ⏳ Phase 6: Runtime Verification (To be done with environment variables)
- ⏳ Phase 7: Web Validation (Network sniffing for critical unknowns)

**Implementation Phase (To Begin):**
- 🔮 Phase 9: Implementation Starter (Code scaffolding + API wrapper)

---

## Next Steps

1. **Validate Critical Items** (Phases 6-7)
   - Sniff web app API calls
   - Document position scale
   - Identify stop command mechanism
   - Update research docs with findings

2. **Begin Implementation** (Phase 9)
   - Python API abstraction
   - HA custom component skeleton
   - Remote connection implementation
   - Local connection implementation
   - Dual mode fallback

3. **Test & Release**
   - Unit and integration tests
   - Hardware validation
   - HACS package setup
   - Documentation completion

---

## Resources

**Official:**
- Web App: https://exalushome.tr7.pl/
- npm Profile: https://www.npmjs.com/~zamel
- npm Packages: lavva.exalushome, lavva.exalushome.portos, etc.

**HA Development:**
- Custom Components: https://developers.home-assistant.io/docs/creating_component_index
- CoverEntity: https://developers.home-assistant.io/docs/core/entity/cover/
- Config Flow: https://developers.home-assistant.io/docs/configuration_flow_index/

---

## Questions?

See `research/` for detailed technical documentation and `IMPLEMENTATION_STARTER.md` for validation methods and code starter examples.

All analysis and documentation is in this repository. See STATUS_REPORT.md for comprehensive completion report.
