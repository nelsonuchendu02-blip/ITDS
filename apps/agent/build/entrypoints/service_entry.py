"""PyInstaller entry point for the frozen `ITDSAgent.exe` service binary.

PyInstaller freezes whatever script it is pointed at as the `__main__`
module, which breaks package-relative imports (`from ..core.bootstrap
import build_runtime`, `from .lifecycle import ...`) inside
`itds_agent.service.host` if that module were passed to PyInstaller
directly. This tiny wrapper is frozen as `__main__` instead and imports
`itds_agent.service.host` the normal, absolute way, so the package's
internal relative imports resolve exactly as they do when run via
`python -m itds_agent`. See `build/build_exe.py`.
"""
from __future__ import annotations

from itds_agent.service.host import main

if __name__ == "__main__":
    main()
