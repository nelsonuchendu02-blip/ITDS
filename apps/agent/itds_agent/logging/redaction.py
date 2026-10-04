from __future__ import annotations

import logging
import re

#: Redaction patterns for values that must never reach a log line, even if a
#: caller accidentally interpolates a credential or header into a message.
#: This is defense in depth - call sites should never log secrets in the
#: first place - but a redacting filter means a mistake degrades safely
#: instead of leaking a credential to disk or Windows Event Log.
_REDACTION_PATTERNS = [
    re.compile(r"(X-Agent-Credential\s*[:=]\s*)([^\s,;]+)", re.IGNORECASE),
    re.compile(r"(Authorization\s*[:=]\s*)([^\s,;]+)", re.IGNORECASE),
    re.compile(r"(credential\s*[:=]\s*)([^\s,;]+)", re.IGNORECASE),
    re.compile(r"(password\s*[:=]\s*)([^\s,;]+)", re.IGNORECASE),
    re.compile(r"(secret\s*[:=]\s*)([^\s,;]+)", re.IGNORECASE),
    re.compile(r"(token\s*[:=]\s*)([^\s,;]+)", re.IGNORECASE),
]


def redact(message: str) -> str:
    redacted = message
    for pattern in _REDACTION_PATTERNS:
        redacted = pattern.sub(r"\1[redacted]", redacted)
    return redacted


class RedactingFilter(logging.Filter):
    """Rewrites any credential-shaped substring out of a log record.

    Applied to every handler so redaction happens regardless of whether the
    destination is a file, the console, or the Windows Event Log.
    """

    def filter(self, record: logging.LogRecord) -> bool:
        if isinstance(record.msg, str):
            record.msg = redact(record.msg)
        if record.args:
            # Non-string args (e.g. an exception instance passed to
            # `logger.warning("... %s", exc)`) are stringified *here* and
            # redacted immediately. Left as-is, `%`-style formatting only
            # calls `str(arg)` later inside `Handler.emit()`, which runs
            # after this filter - any secret embedded in that object's
            # `__str__` would otherwise reach the log unredacted. Passing
            # an already-redacted string through `%s` is a safe no-op.
            record.args = tuple(redact(str(arg)) for arg in record.args)
        return True
