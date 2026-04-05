"""Auto-detect platform and return the appropriate specs collector."""

from __future__ import annotations

import platform

from .base import BaseSpecsCollector


def get_collector() -> BaseSpecsCollector:
    """Return the specs collector for the current platform."""
    system = platform.system()

    if system == "Windows":
        from .windows import WindowsSpecsCollector
        return WindowsSpecsCollector()

    if system == "Darwin":
        raise NotImplementedError(
            "macOS support coming soon. "
            "Contributions welcome: implement specs/macos.py"
        )

    if system == "Linux":
        raise NotImplementedError(
            "Linux support coming soon. "
            "Contributions welcome: implement specs/linux.py"
        )

    raise NotImplementedError(f"Unsupported platform: {system}")
