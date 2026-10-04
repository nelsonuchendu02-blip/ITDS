"""PyInstaller build script for ITDSAgent.exe.

Produces a directory-based deployment package (not a single-file exe):
`--onedir` starts faster, is easier to inspect/debug, and lets an installer
add/replace individual files without repackaging, which better serves the
"clear output directory" and "documented build commands" requirements than a
single-file executable would.

Usage (from apps/agent):
    pip install -r requirements.txt
    pip install -r build/requirements-build.txt
    python build/build_exe.py

Output:
- apps/agent/build/dist/ITDSAgent/ITDSAgent.exe - the service/SCM binary.
- apps/agent/build/dist/ITDSAgentEnroll/ITDSAgentEnroll.exe - the one-time
  operator tool that stores the protected credential (see
  itds_agent/security/enroll.py).

Nothing here embeds a credential, a production API URL, or any other
secret; the frozen executables read external configuration/credentials
exactly like console mode (see docs/operations/windows-agent.md).
"""
from __future__ import annotations

import subprocess  # noqa: S404 - build-tooling script, not part of the shipped agent
import sys
from pathlib import Path

BUILD_DIR = Path(__file__).parent
AGENT_ROOT = BUILD_DIR.parent
ENTRYPOINTS_DIR = BUILD_DIR / "entrypoints"
# Thin, absolute-import wrapper scripts (see entrypoints/*.py) are used as
# the actual PyInstaller entry scripts instead of pointing PyInstaller
# directly at itds_agent/service/host.py or itds_agent/security/enroll.py,
# because PyInstaller freezes its entry script as `__main__`, which breaks
# those modules' package-relative imports.
SERVICE_ENTRY_SCRIPT = ENTRYPOINTS_DIR / "service_entry.py"
ENROLL_ENTRY_SCRIPT = ENTRYPOINTS_DIR / "enroll_entry.py"


def _run_pyinstaller(name: str, entry_script: Path, *extra_hidden_imports: str) -> int:
    args = [
        sys.executable,
        "-m",
        "PyInstaller",
        "--noconfirm",
        "--clean",
        "--name",
        name,
        "--onedir",
        "--console",
        "--distpath",
        str(BUILD_DIR / "dist"),
        "--workpath",
        str(BUILD_DIR / "work"),
        "--specpath",
        str(BUILD_DIR),
        # Makes `import itds_agent` resolve inside the frozen entry-point
        # wrapper scripts, which live outside the itds_agent package.
        "--paths",
        str(AGENT_ROOT),
    ]
    for hidden_import in extra_hidden_imports:
        args += ["--hidden-import", hidden_import]
    args.append(str(entry_script))
    print("Running:", " ".join(args))
    result = subprocess.run(args, cwd=AGENT_ROOT, check=False)  # noqa: S603 - fixed, non-shell argv
    return result.returncode


def main() -> int:
    if sys.platform != "win32":
        print("ITDSAgent.exe can only be built on Windows (pywin32 is a Windows-only dependency).")
        return 1

    # pywin32's service plumbing relies on dynamic imports PyInstaller's
    # static analysis cannot always discover on its own.
    service_rc = _run_pyinstaller("ITDSAgent", SERVICE_ENTRY_SCRIPT, "win32timezone", "servicemanager")
    if service_rc != 0:
        return service_rc

    return _run_pyinstaller("ITDSAgentEnroll", ENROLL_ENTRY_SCRIPT)


if __name__ == "__main__":
    raise SystemExit(main())
