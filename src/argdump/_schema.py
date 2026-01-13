"""Schema version constants and environment metadata."""

from __future__ import annotations

import platform
from dataclasses import dataclass

SCHEMA_URL_V1 = "https://childmindresearch.github.io/argdump/schema-v1.json"


@dataclass
class EnvironmentInfo:
    """Information about the Python environment where serialization occurred."""

    python_version: str
    python_implementation: str
    platform_system: str
    platform_release: str
    platform_machine: str
    argdump_version: str


def get_environment_info() -> EnvironmentInfo:
    """Capture current environment information."""
    from . import __version__

    return EnvironmentInfo(
        python_version=platform.python_version(),
        python_implementation=platform.python_implementation(),
        platform_system=platform.system(),
        platform_release=platform.release(),
        platform_machine=platform.machine(),
        argdump_version=__version__,
    )
