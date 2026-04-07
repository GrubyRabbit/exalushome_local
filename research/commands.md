# ExalusHome Shutter/Blind Commands & Tasks

## Overview
Shutter/blind control is implemented via the Task execution system. Devices declare supported task types,
channels execute tasks, and task execution results are reported asynchronously.

---

## Device Roles for Shutters

From `IDeviceChannel` enum:

```typescript
enum Roles {
    Blind = 11,
    Roller = 12,
    BlindsWithPrecisePosition = 21,
    BlindsRemote = 23,
    // ... others
}
```

**Key Roles for Integration:**
- **Blind (11)** — Standard blind/shutter device
- **Roller (12)** — Roller shutter variant
- **BlindsWithPrecisePosition (21)** — Supports position feedback/control
- **BlindsRemote (23)** — Remote control for blinds

---

## Shutter Task Types (Commands)

Based on `DeviceTaskType` enum:

### Position Control

#### SetBlindPosition
- **Interface Type:** `IBlindPosition`
- **Purpose:** Set blind to exact position
- **Payload:** Position value (scale TBD: 0-100%? 0-255? other?)
- **Response:** Execution result (in progress, success, failure)
- **Availability:** Check `device.AvailableTaskTypes` for `SetBlindPosition`

#### SetBlindPositionSimple
- **Interface Type:** `IBlindPositionSimple`
- **Purpose:** Simplified position control (likely open/close/stop only)
- **Payload:** Position enum or simple command
- **Response:** Execution result

#### SetBlindMicroventilation
- **Interface Type:** `IMicroventilation`
- **Purpose:** Tilt blind slats for ventilation/partial opening
- **Payload:** Ventilation angle or level
- **Response:** Execution result

### Timing & Configuration

#### SetBlindOpenCloseTime
- **Interface Type:** `ISetBlindOpenCloseTime`
- **Purpose:** Configure how long it takes to fully open/close
- **Payload:** Time in seconds (or milliseconds)
- **Use Case:** Calibrate timing for position calculations

---

## State/Response Types

From `DeviceResponseType` enum:

### Position State

#### BlindPosition
- **Interface Type:** `IBlindPosition`
- **Data:** Current position value
- **Scale:** Unknown — NEEDS VALIDATION
  - Possibly 0-100 (percentage)
  - Possibly 0-255 (raw value)
  - Possibly 0-180 (angle in degrees)
  - Possibly other device-specific scale
- **Update Frequency:** On change, or periodic polling
- **Availability:** Check `channel.AvailableResponseTypes`

### Configuration State

#### BlindOpenCloseTime
- **Interface Type:** `IBlindOpenCloseTime`
- **Data:** Timing configuration (seconds to fully open/close)

#### BlindCalibration
- **Interface Type:** `BlindCalibration`
- **Data:** Calibration state (calibrated? needs calibration?)

### Error States

#### BlindErrorState
- **Interface Type:** `IBlindError`
- **Data:** Error flags (motor stalled? obstruction? mechanical failure?)

#### BlindRemoteButtonState
- **Interface Type:** `IBlindsControlButton`
- **Data:** Remote control button state (which button pressed?)

---

## Task Execution Model

### Creating a Task

```typescript
// 1. Get device and channel
const device: IDevice = /* ... */;
const channel: IDeviceChannel = device.Channels[0];

// 2. Check if device supports the task type
const supportsPosition = channel.AvailableTaskTypes.some(
    t => t.Type === DeviceTaskType.SetBlindPosition
);
if (!supportsPosition) {
    console.error("Device does not support SetBlindPosition");
}

// 3. Create task object (structure TBD)
const task: IDeviceTask = {
    Type: DeviceTaskType.SetBlindPosition,
    InterfaceType: "IBlindPosition",
    // Payload varies by task type
    // For SetBlindPosition: { position: 50 }
};

// 4. Execute task
const result: DeviceTaskExecutionResult = await channel.ExecuteTaskAsync(task);
```

### Task Execution Result

```typescript
enum DeviceTaskExecutionResult {
    // Values TBD from source
    // Expected: Success, InProgress, Failed, NotSupported, etc.
}
```

---

## State Change Notifications

### Channel-Level Events

```typescript
// Single state change
channel.OnChannelStateChangedEvent().subscribe((state: IDeviceState) => {
    if (state.Type === DeviceResponseType.BlindPosition) {
        console.log("Position changed:", state.Data);
    }
});

// State refreshed or changed (includes periodic updates)
channel.OnChannelStateRefreshedOrChangedEvent().subscribe((state: IDeviceState) => {
    console.log("State update:", state);
});

// Task execution status
channel.OnTasksExecutionChangeEvent().subscribe((execution: TaskExecution) => {
    if (execution === TaskExecution.ExecutingTasks) {
        console.log("Device is moving blind...");
    } else {
        console.log("Movement complete");
    }
});
```

### Device-Level Events

```typescript
// Any state on any channel changes
device.OnDeviceStateChangedEvent().subscribe((state: IDeviceState) => {
    // Handle state change
});

// Refreshed or changed (includes polling)
device.OnDeviceStateRefreshedOrChangedEvent().subscribe((state: IDeviceState) => {
    // Handle update
});

// Task execution change
device.OnDeviceTasks ExecutionChangedOnChannelsEvent().subscribe(
    (channelIds: number[]) => {
        console.log("Channels executing tasks:", channelIds);
    }
);
```

---

## Typical Blind Operations

### Open Blind (100% open)
```typescript
const task: IDeviceTask = {
    Type: DeviceTaskType.SetBlindPosition,
    InterfaceType: "IBlindPosition",
    Data: { position: 100 }  // or 0, depending on scale
};
await channel.ExecuteTaskAsync(task);
```

### Close Blind (0% open)
```typescript
const task: IDeviceTask = {
    Type: DeviceTaskType.SetBlindPosition,
    InterfaceType: "IBlindPosition",
    Data: { position: 0 }  // or 100, depending on scale
};
await channel.ExecuteTaskAsync(task);
```

### Set to 50% (Half Open)
```typescript
const task: IDeviceTask = {
    Type: DeviceTaskType.SetBlindPosition,
    InterfaceType: "IBlindPosition",
    Data: { position: 50 }
};
await channel.ExecuteTaskAsync(task);
```

### Stop Movement (if supported)
```typescript
// Likely via SetBlindPositionSimple or special position value
// TBD: Exact mechanism
```

### Enable Microventilation
```typescript
const task: IDeviceTask = {
    Type: DeviceTaskType.SetBlindMicroventilation,
    InterfaceType: "IMicroventilation",
    Data: { angle: 15 }  // or percentage, scale TBD
};
await channel.ExecuteTaskAsync(task);
```

---

## Position Scale (CRITICAL — MUST VALIDATE)

**Current assumption:** 0-100 percentage
**Alternatives:**
- 0-255 (8-bit resolution)
- 0-180 (degrees, tilt angle)
- Device-specific calibrated values
- Enum (closed/opening/open/closing/stopped)

**Action Required:**
1. Sniff web app API calls to observe position values
2. Check device response types for position constraints
3. Test with physical controller if available
4. Check Portos package for position semantics

---

## Channel Grouping (Multi-Channel Devices)

Some devices have multiple channels (e.g., multiple blinds per motor):

```typescript
// Get all channels
const channels = device.Channels;

// Get channel groups
const groups = channel.ChannelGroups;

// Device can indicate if channels should be grouped
const shouldGroup = device.ShouldChannelsBeGrouped;
```

**For HA Integration:**
- Consider each channel as a separate `CoverEntity`
- Or group them if device indicates it's a multi-blind unit

---

## Advanced: Custom Data & Roles

Channels can have custom data and roles:

```typescript
// Get custom data
const customData = channel.CustomData;  // Record<string, string>

// Get roles (capabilities)
const roles = channel.Roles;  // Roles[]

// Has custom data support?
if (channel.IsCustomDataAndRolesSupported()) {
    // Can set custom data
    const result = await channel.SetCustomDataAsync("key", "value");
}
```

**Use Case:** Storing HA-specific metadata or room assignments.

---

## Known Issues & TODOs

- [ ] Extract exact `IDeviceTask` interface structure
- [ ] Extract exact `DeviceTaskExecutionResult` enum
- [ ] Determine position scale (0-100? 0-255? other?)
- [ ] Validate stop command mechanism (SetBlindPositionSimple? special value?)
- [ ] Extract error code meanings
- [ ] Confirm task types available on real controllers
- [ ] Determine state update frequency (polling? push? both?)
- [ ] Extract state value ranges for each response type
- [ ] Test multi-channel device behavior
