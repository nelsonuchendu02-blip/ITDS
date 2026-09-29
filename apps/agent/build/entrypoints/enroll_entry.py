"""PyInstaller entry point for the frozen `ITDSAgentEnroll.exe` binary.

See `service_entry.py` for why a thin, absolute-import wrapper script is
required instead of pointing PyInstaller directly at
`itds_agent/security/enroll.py` (which uses package-relative imports).
"""
from __future__ import annotations

import sys

from itds_agent.security.enroll import main

if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
