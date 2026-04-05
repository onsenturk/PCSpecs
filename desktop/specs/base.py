"""Platform abstraction for hardware specs collection.

Provides a common interface so OS-specific backends (Windows, macOS, Linux)
can be swapped without changing the rest of the application.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field


@dataclass
class CpuInfo:
    brand: str = "Unknown"
    cores: int = 0
    threads: int = 0
    frequency_mhz: float = 0.0
    architecture: str = "Unknown"


@dataclass
class GpuInfo:
    name: str = "Unknown"
    vram_total_mb: float = 0.0
    vram_used_mb: float = 0.0
    temperature_c: float | None = None
    load_percent: float | None = None
    driver_version: str = ""


@dataclass
class MemoryInfo:
    total_bytes: int = 0
    available_bytes: int = 0
    used_bytes: int = 0
    percent: float = 0.0
    speed_mhz: int | None = None
    slots: list[dict] = field(default_factory=list)


@dataclass
class StorageInfo:
    device: str = ""
    mountpoint: str = ""
    filesystem: str = ""
    total_bytes: int = 0
    used_bytes: int = 0
    free_bytes: int = 0
    percent: float = 0.0
    drive_type: str = "Unknown"  # SSD / HDD / NVMe / Unknown


@dataclass
class MotherboardInfo:
    manufacturer: str = "Unknown"
    model: str = "Unknown"
    serial: str = ""


@dataclass
class BiosInfo:
    manufacturer: str = "Unknown"
    version: str = "Unknown"
    release_date: str = ""


@dataclass
class OsInfo:
    name: str = "Unknown"
    version: str = ""
    build: str = ""
    architecture: str = ""


@dataclass
class NetworkAdapter:
    name: str = ""
    ip_address: str = ""
    mac_address: str = ""
    speed_mbps: int | None = None
    is_up: bool = False


@dataclass
class BatteryInfo:
    percent: float | None = None
    plugged_in: bool = False
    time_remaining_sec: int | None = None
    has_battery: bool = False


@dataclass
class LiveMetrics:
    cpu_usage_percent: float = 0.0
    cpu_per_core: list[float] = field(default_factory=list)
    cpu_frequency_mhz: float = 0.0
    ram_used_bytes: int = 0
    ram_percent: float = 0.0
    gpu_metrics: list[dict] = field(default_factory=list)
    disk_read_bytes_sec: float = 0.0
    disk_write_bytes_sec: float = 0.0
    net_sent_bytes_sec: float = 0.0
    net_recv_bytes_sec: float = 0.0
    battery: BatteryInfo | None = None


class BaseSpecsCollector(ABC):
    """Abstract base class for platform-specific hardware detection."""

    @abstractmethod
    def get_cpu(self) -> CpuInfo: ...

    @abstractmethod
    def get_gpu(self) -> list[GpuInfo]: ...

    @abstractmethod
    def get_memory(self) -> MemoryInfo: ...

    @abstractmethod
    def get_storage(self) -> list[StorageInfo]: ...

    @abstractmethod
    def get_motherboard(self) -> MotherboardInfo: ...

    @abstractmethod
    def get_bios(self) -> BiosInfo: ...

    @abstractmethod
    def get_os(self) -> OsInfo: ...

    @abstractmethod
    def get_network(self) -> list[NetworkAdapter]: ...

    @abstractmethod
    def get_battery(self) -> BatteryInfo: ...

    @abstractmethod
    def get_live_metrics(self) -> LiveMetrics: ...

    def get_all_static(self) -> dict:
        """Collect all static (non-changing) hardware specs at once."""
        return {
            "cpu": self.get_cpu().__dict__,
            "gpu": [g.__dict__ for g in self.get_gpu()],
            "memory": self.get_memory().__dict__,
            "storage": [s.__dict__ for s in self.get_storage()],
            "motherboard": self.get_motherboard().__dict__,
            "bios": self.get_bios().__dict__,
            "os": self.get_os().__dict__,
            "network": [n.__dict__ for n in self.get_network()],
            "battery": self.get_battery().__dict__,
        }
