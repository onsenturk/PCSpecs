"""Windows hardware specs collector using WMI, psutil, GPUtil, and py-cpuinfo."""

from __future__ import annotations

import platform
import time

import cpuinfo
import psutil

from .base import (
    BaseSpecsCollector,
    BatteryInfo,
    BiosInfo,
    CpuInfo,
    GpuInfo,
    LiveMetrics,
    MemoryInfo,
    MotherboardInfo,
    NetworkAdapter,
    OsInfo,
    StorageInfo,
)


class WindowsSpecsCollector(BaseSpecsCollector):
    def __init__(self) -> None:
        self._prev_disk_io = psutil.disk_io_counters()
        self._prev_net_io = psutil.net_io_counters()
        self._prev_time = time.monotonic()

    # --- WMI helpers (lazy-loaded) ---

    def _wmi(self):
        """Lazy-load WMI connection."""
        if not hasattr(self, "_wmi_conn"):
            import wmi
            self._wmi_conn = wmi.WMI()
        return self._wmi_conn

    def _wmi_query(self, query: str) -> list:
        try:
            return self._wmi().query(query)
        except Exception:
            return []

    # --- Static specs ---

    def get_cpu(self) -> CpuInfo:
        try:
            info = cpuinfo.get_cpu_info()
        except Exception:
            info = {}

        freq = psutil.cpu_freq()
        return CpuInfo(
            brand=info.get("brand_raw", "Unknown"),
            cores=psutil.cpu_count(logical=False) or 0,
            threads=psutil.cpu_count(logical=True) or 0,
            frequency_mhz=freq.max if freq else 0.0,
            architecture=info.get("arch", platform.machine()),
        )

    def get_gpu(self) -> list[GpuInfo]:
        gpus: list[GpuInfo] = []

        # Try NVIDIA via GPUtil
        try:
            import GPUtil
            for g in GPUtil.getGPUs():
                gpus.append(GpuInfo(
                    name=g.name,
                    vram_total_mb=g.memoryTotal,
                    vram_used_mb=g.memoryUsed,
                    temperature_c=g.temperature,
                    load_percent=round(g.load * 100, 1),
                    driver_version=g.driver,
                ))
        except Exception:
            pass

        # WMI fallback for AMD / Intel / any GPU not caught above
        try:
            nvidia_names = {g.name.lower() for g in gpus}
            results = self._wmi_query(
                "SELECT Description, AdapterRAM, DriverVersion "
                "FROM Win32_VideoController"
            )
            for vc in results:
                desc = vc.Description or "Unknown GPU"
                if desc.lower() in nvidia_names:
                    continue
                vram = 0.0
                try:
                    vram = (int(vc.AdapterRAM) or 0) / (1024 * 1024)
                except (TypeError, ValueError):
                    pass
                gpus.append(GpuInfo(
                    name=desc,
                    vram_total_mb=vram,
                    driver_version=vc.DriverVersion or "",
                ))
        except Exception:
            pass

        if not gpus:
            gpus.append(GpuInfo(name="No GPU detected"))

        return gpus

    def get_memory(self) -> MemoryInfo:
        vm = psutil.virtual_memory()
        info = MemoryInfo(
            total_bytes=vm.total,
            available_bytes=vm.available,
            used_bytes=vm.used,
            percent=vm.percent,
        )

        # Get RAM speed and slot info via WMI
        try:
            sticks = self._wmi_query(
                "SELECT Capacity, Speed, Manufacturer, DeviceLocator "
                "FROM Win32_PhysicalMemory"
            )
            slots = []
            for stick in sticks:
                cap = 0
                try:
                    cap = int(stick.Capacity) if stick.Capacity else 0
                except (TypeError, ValueError):
                    pass
                spd = 0
                try:
                    spd = int(stick.Speed) if stick.Speed else 0
                except (TypeError, ValueError):
                    pass
                slots.append({
                    "capacity_bytes": cap,
                    "speed_mhz": spd,
                    "manufacturer": stick.Manufacturer or "Unknown",
                    "slot": stick.DeviceLocator or "",
                })
                if spd and not info.speed_mhz:
                    info.speed_mhz = spd
            info.slots = slots
        except Exception:
            pass

        return info

    def get_storage(self) -> list[StorageInfo]:
        drives: list[StorageInfo] = []

        # Detect drive types via MSFT_PhysicalDisk (accurate SSD/HDD/NVMe)
        # MediaType: 0=Unspecified, 3=HDD, 4=SSD; BusType: 17=NVMe
        disk_types: dict[int, str] = {}
        try:
            import wmi as _wmi
            storage_ns = _wmi.WMI(namespace="root/microsoft/windows/storage")
            for pd in storage_ns.query(
                "SELECT DeviceId, MediaType, BusType FROM MSFT_PhysicalDisk"
            ):
                media = int(pd.MediaType) if pd.MediaType is not None else 0
                bus = int(pd.BusType) if pd.BusType is not None else 0
                dev_id = int(pd.DeviceId) if pd.DeviceId is not None else -1
                if media == 4:
                    disk_types[dev_id] = "NVMe" if bus == 17 else "SSD"
                elif media == 3:
                    disk_types[dev_id] = "HDD"
                else:
                    disk_types[dev_id] = "Unknown"
        except Exception:
            pass

        # Map drive letters to disk types via MSFT_Partition
        letter_to_type: dict[str, str] = {}
        try:
            import wmi as _wmi
            storage_ns = _wmi.WMI(namespace="root/microsoft/windows/storage")
            for mpart in storage_ns.query(
                "SELECT DiskNumber, DriveLetter FROM MSFT_Partition"
            ):
                letter_code = int(mpart.DriveLetter) if mpart.DriveLetter is not None else 0
                disk_num = int(mpart.DiskNumber) if mpart.DiskNumber is not None else -1
                if letter_code > 0 and disk_num >= 0:
                    letter = chr(letter_code)
                    letter_to_type[f"{letter}:\\"] = disk_types.get(disk_num, "Unknown")
        except Exception:
            pass

        for part in psutil.disk_partitions(all=False):
            try:
                usage = psutil.disk_usage(part.mountpoint)
            except (PermissionError, OSError):
                continue

            dtype = letter_to_type.get(part.mountpoint, "Unknown")

            drives.append(StorageInfo(
                device=part.device,
                mountpoint=part.mountpoint,
                filesystem=part.fstype,
                total_bytes=usage.total,
                used_bytes=usage.used,
                free_bytes=usage.free,
                percent=usage.percent,
                drive_type=dtype,
            ))

        return drives

    def get_motherboard(self) -> MotherboardInfo:
        try:
            results = self._wmi_query(
                "SELECT Manufacturer, Product, SerialNumber "
                "FROM Win32_BaseBoard"
            )
            if results:
                mb = results[0]
                return MotherboardInfo(
                    manufacturer=mb.Manufacturer or "Unknown",
                    model=mb.Product or "Unknown",
                    serial=mb.SerialNumber or "",
                )
        except Exception:
            pass
        return MotherboardInfo()

    def get_bios(self) -> BiosInfo:
        try:
            results = self._wmi_query(
                "SELECT Manufacturer, SMBIOSBIOSVersion, ReleaseDate "
                "FROM Win32_BIOS"
            )
            if results:
                b = results[0]
                date_raw = b.ReleaseDate or ""
                # WMI dates: "20231015000000.000000+000"
                date_str = date_raw[:8] if len(date_raw) >= 8 else date_raw
                if len(date_str) == 8:
                    date_str = f"{date_str[:4]}-{date_str[4:6]}-{date_str[6:8]}"
                return BiosInfo(
                    manufacturer=b.Manufacturer or "Unknown",
                    version=b.SMBIOSBIOSVersion or "Unknown",
                    release_date=date_str,
                )
        except Exception:
            pass
        return BiosInfo()

    def get_os(self) -> OsInfo:
        return OsInfo(
            name=f"{platform.system()} {platform.release()}",
            version=platform.version(),
            build=platform.win32_ver()[1] if hasattr(platform, "win32_ver") else "",
            architecture=platform.machine(),
        )

    def get_network(self) -> list[NetworkAdapter]:
        adapters: list[NetworkAdapter] = []
        stats = psutil.net_if_stats()
        addrs = psutil.net_if_addrs()

        for name, nic_addrs in addrs.items():
            ip = ""
            mac = ""
            for a in nic_addrs:
                if a.family.name == "AF_INET":
                    ip = a.address
                elif a.family.name == "AF_LINK":
                    mac = a.address

            nic_stat = stats.get(name)
            adapters.append(NetworkAdapter(
                name=name,
                ip_address=ip,
                mac_address=mac,
                speed_mbps=nic_stat.speed if nic_stat else None,
                is_up=nic_stat.isup if nic_stat else False,
            ))

        return adapters

    def get_battery(self) -> BatteryInfo:
        bat = psutil.sensors_battery()
        if bat is None:
            return BatteryInfo(has_battery=False)
        return BatteryInfo(
            percent=bat.percent,
            plugged_in=bat.power_plugged,
            time_remaining_sec=bat.secsleft if bat.secsleft != psutil.POWER_TIME_UNLIMITED else None,
            has_battery=True,
        )

    # --- Live metrics ---

    def get_live_metrics(self) -> LiveMetrics:
        now = time.monotonic()
        dt = now - self._prev_time
        if dt <= 0:
            dt = 0.5
        self._prev_time = now

        # CPU
        cpu_pct = psutil.cpu_percent(interval=None)
        cpu_per_core = psutil.cpu_percent(interval=None, percpu=True)
        freq = psutil.cpu_freq()

        # RAM
        vm = psutil.virtual_memory()

        # GPU live metrics
        gpu_metrics: list[dict] = []
        try:
            import GPUtil
            for g in GPUtil.getGPUs():
                gpu_metrics.append({
                    "name": g.name,
                    "temperature_c": g.temperature,
                    "load_percent": round(g.load * 100, 1),
                    "vram_used_mb": g.memoryUsed,
                    "vram_total_mb": g.memoryTotal,
                })
        except Exception:
            pass

        # Disk I/O rates
        disk_io = psutil.disk_io_counters()
        disk_read = (disk_io.read_bytes - self._prev_disk_io.read_bytes) / dt if disk_io else 0
        disk_write = (disk_io.write_bytes - self._prev_disk_io.write_bytes) / dt if disk_io else 0
        if disk_io:
            self._prev_disk_io = disk_io

        # Network rates
        net_io = psutil.net_io_counters()
        net_sent = (net_io.bytes_sent - self._prev_net_io.bytes_sent) / dt if net_io else 0
        net_recv = (net_io.bytes_recv - self._prev_net_io.bytes_recv) / dt if net_io else 0
        if net_io:
            self._prev_net_io = net_io

        # Battery
        bat = self.get_battery()

        return LiveMetrics(
            cpu_usage_percent=cpu_pct,
            cpu_per_core=cpu_per_core,
            cpu_frequency_mhz=freq.current if freq else 0.0,
            ram_used_bytes=vm.used,
            ram_percent=vm.percent,
            gpu_metrics=gpu_metrics,
            disk_read_bytes_sec=max(0, disk_read),
            disk_write_bytes_sec=max(0, disk_write),
            net_sent_bytes_sec=max(0, net_sent),
            net_recv_bytes_sec=max(0, net_recv),
            battery=bat,
        )
