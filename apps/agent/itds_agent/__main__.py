"""Console-mode entry point: ``python -m itds_agent``.

Runs the exact same `AgentRuntime` lifecycle as the Windows service host
(both are built by `core.bootstrap.build_runtime`), which makes this mode
suitable for development and troubleshooting without maintaining a second
implementation of the agent lifecycle.

Fails cleanly (a clear, non-zero-exit error message, no traceback dump of
secrets) when required configuration or an enrolled credential is absent.
"""
from __future__ import annotations

import signal
import sys

from .config.loader import ConfigurationError
from .core.bootstrap import build_runtime


def main(argv: list[str] | None = None) -> int:
    try:
        runtime = build_runtime()
    except ConfigurationError as exc:
        print(f"itds-agent: configuration error: {exc}", file=sys.stderr)
        return 2

    def _handle_signal(signum, _frame):
        runtime.logger.info("received shutdown signal %s; stopping", signum)
        runtime.stop()

    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            signal.signal(sig, _handle_signal)
        except (ValueError, OSError):
            # Some signals are unavailable on certain platforms/threads;
            # the runtime remains stoppable via its own stop() method.
            continue

    runtime.logger.info("itds-agent starting in console mode (version %s)", runtime.settings.agent_version)
    runtime.run()
    runtime.logger.info("itds-agent stopped")
    return 0 if runtime.state.value != "error" else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
