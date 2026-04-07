# ExalusHome Entities & State Models

## Device Entity Structure

### Base Device Properties
```typescript
interface IDevice {
  Guid: string;                          // Unique device ID
  Name: string;                          // User-defined name
  IconType: IconType;                    // Icon enum for UI
  SerialNumber: string | null;           // Hardware serial
  SoftwareVersion: string | null;        // Firmware version
  Model: string | null;                  // Device model
  ModelGuid: string | null;              // Model identifier
  ManufacturerGuid: string | null;       // Manufacturer ID
  IsVirtual: boolean;                    // Is virtual device
  IsEnabled: boolean;                    // Is enabled
  DeviceState: DeviceState;              // Working/Broken/NotResponding
  DeviceType: DeviceType;                // Device category
  CommunicationWay: CommunicationWay;    // OneWay/TwoWay/Conditional
  Channels: IDeviceChannel[];            // Control channels
  States: IDeviceState<T>[];             // Current state values
}
```

### DeviceState Enum
```
NotResponding = 0
Working = 1
Broken = 2
FirmwareUpgradeMode = 3
```

### Availability
- Reflected via `DeviceState` field
- `Working` = available/on
- `NotResponding` = unavailable/off
- `Broken` = error state

---

## Device Channels

Devices have multiple channels for different controls:

```typescript
interface IDeviceChannel {
  Guid: string;
  Name: string;
  ChannelNumber: number;
  IconType: IconType;
  IsAvailable: boolean;
  IsLocked: boolean;
  ChannelType: ChannelType;
  // Task execution for this channel
  ExecuteTaskAsync(task: IDeviceTask): Promise<...>;
}
```

---

## Shutter/Blind-Specific

### Task Types (Commands Available)

#### SetBlindPosition
- **Interface:** `IBlindPosition`
- **Purpose:** Set blind to specific position
- **Likely payload:** position (numeric value)
- **Availability:** Check `AvailableTaskTypes` in device

#### SetBlindPositionSimple
- **Interface:** `IBlindPositionSimple`
- **Purpose:** Simplified position control
- **May be:** open/close/stop only (no percentage)

#### SetBlindMicroventilation
- **Interface:** `IMicroventilation`
- **Purpose:** Tilt blind slats for ventilation
- **Likely payload:** microventilation angle

#### SetBlindOpenCloseTime
- **Interface:** `ISetBlindOpenCloseTime`
- **Purpose:** Configure open/close timing
- **Payload:** time values

### Response Types (State Information)

#### BlindPosition
- **Interface:** `IBlindPosition`
- **Contains:** Current position value
- **Scale:** Unknown (0-100? 0-255? 0-180?)
- **Availability:** Check `AvailableResponseTypes`

#### BlindOpenCloseTime
- **Interface:** `IBlindOpenCloseTime`
- **Contains:** Timing configuration

#### BlindErrorState
- **Interface:** `IBlindError`
- **Contains:** Error condition flags

#### BlindRemoteButtonState
- **Interface:** `IBlindsControlButton`
- **Contains:** Remote control state

---

## State Change Notification

### Events
```typescript
device.OnDeviceStateChangedEvent().subscribe((newState: IDeviceState) => {
  // Handle state change
});

device.OnDeviceStateRefreshedOrChangedEvent().subscribe((state: IDeviceState) => {
  // State refreshed or changed
});
```

### State Container
```typescript
interface IDeviceState<T> {
  Type: DeviceResponseType;  // What kind of state (e.g., BlindPosition)
  InterfaceType: string;     // Interface name
  Data: T;                   // Actual state value
  Timestamp: number;         // When this state was received
}
```
Note: Double braces `{` and `}` are used to escape in f-string contexts.

---

## Device Discovery

**To be determined:**
- How devices are enumerated
- Device filtering by type
- Device filtering by capability
- Bulk state fetch vs. streaming updates

---

## Position Semantics

**Critical unknown:**
- Is position 0-100 percentage? (0 = open, 100 = closed)?
- Or is it 0-255 raw value?
- Or is it 0-180 angle in degrees?
- Does direction vary by device type?
- Is there a device.tilt property separate from position?

---

## Next Steps

1. Extract `IBlindPosition` interface definition
2. Find device discovery service API
3. Extract state polling/subscription patterns
4. Determine position scale from example payloads
5. Analyze open/close/stop command patterns
