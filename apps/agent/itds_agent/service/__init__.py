"""Windows service integration for the ITDS endpoint agent.

`lifecycle.py` is Windows-agnostic and unit-testable on any platform.
`host.py` is the thin `pywin32`-dependent wrapper registered with the
Windows Service Control Manager; it is only importable on Windows.
"""
from .lifecycle import ServiceLifecycle, ServiceLifecycleError

__all__ = ["ServiceLifecycle", "ServiceLifecycleError"]
