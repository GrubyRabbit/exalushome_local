"""Data models for ExalusHome Local API."""

from dataclasses import dataclass, field
from enum import IntEnum
from typing import Optional, List


class DeviceState(IntEnum):
    """Device state enum."""
    NotResponding = 0
    Working = 1
    Broken = 2
    FirmwareUpgradeMode = 3


class TaskExecution(IntEnum):
    """Task execution state."""
    NoTasksExecuting = 0
    ExecutingTasks = 1


class ControlFeature(IntEnum):
    """Device control features."""
    Unknown = 0
    Blind = 3  # Roller shutter/blind control
    Microventilation = 13  # Producer-captured microventilation command


@dataclass
class BlindPosition:
    """Blind position state."""
    data: int  # Position value in Exalus scale (0=open, 100=closed)


@dataclass
class BlindState:
    """Blind/shutter state snapshot."""
    position: int  # Current position (Exalus scale: 0=open, 100=closed)
    moving: bool = False  # Is currently moving
    timestamp: float = field(default_factory=lambda: 0)


@dataclass
class DeviceChannel:
    """Device channel (individual control element)."""
    guid: str
    number: int
    name: str
    control_feature: ControlFeature = ControlFeature.Unknown
    available: bool = True
    supports_microventilation: bool = False

    def is_blind(self) -> bool:
        """Check if this channel is a blind/shutter."""
        return self.control_feature == ControlFeature.Blind


@dataclass
class Device:
    """ExalusHome device."""
    guid: str
    name: str
    state: DeviceState = DeviceState.NotResponding
    serial_number: Optional[str] = None
    software_version: Optional[str] = None
    model: Optional[str] = None
    channels: List[DeviceChannel] = field(default_factory=list)
    
    def get_blind_channels(self) -> List[DeviceChannel]:
        """Get all blind/shutter channels in this device."""
        return [ch for ch in self.channels if ch.is_blind()]
    
    @property
    def available(self) -> bool:
        """Check if device is available (working)."""
        return self.state == DeviceState.Working


@dataclass
class ShutterDevice:
    """Shutter device for HA integration."""
    device_guid: str
    device_name: str
    channel: DeviceChannel
    current_position: int = 0  # HA scale: 0=closed, 100=open
    is_moving: bool = False
    available: bool = True

    @property
    def supports_microventilation(self) -> bool:
        """Check if this shutter's channel advertises IMicroventilation."""
        return self.channel.supports_microventilation

    @property
    def unique_id(self) -> str:
        """Generate unique ID for HA entity."""
        return f"{self.device_guid}_{self.channel.number}"
    
    @property
    def name(self) -> str:
        """Device name for HA.

        Omits the channel name when it duplicates the device name
        (common for single-channel shutter controllers).
        """
        channel_name = self.channel.name.strip()
        device_name = self.device_name.strip()
        if not channel_name or channel_name == device_name:
            return device_name
        return f"{device_name} {channel_name}"


@dataclass
class ShutterCommand:
    """Command to execute on a shutter."""
    device_guid: str
    channel_number: int
    command_type: int  # 101=open, 102=close, 103=stop, or position value
    
    def is_position_command(self) -> bool:
        """Check if this is a set-position command."""
        return self.command_type not in (101, 102, 103)
    
    def is_stop_command(self) -> bool:
        """Check if this is a stop command."""
        return self.command_type == 103
