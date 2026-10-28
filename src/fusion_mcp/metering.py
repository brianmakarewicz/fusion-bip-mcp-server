"""Append-only metering log — metadata only, never payloads.

Every tool call writes one JSON line: the caller, which tool, when, how long, and
the outcome. It deliberately records NO SQL text, NO parameter values, and NO
report output, so Fusion data never lands here. Inputs are reduced to shape (a
hash and a size).
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import time
from typing import Any

def _default_log() -> str:
    base = os.environ.get("APPDATA") if os.name == "nt" else None
    base = base or os.environ.get("XDG_CONFIG_HOME") or os.path.expanduser("~/.config")
    return os.path.join(base, "fusion-mcp", "metering.jsonl")


_LOG_PATH = os.environ.get("FUSION_MCP_METER_LOG") or _default_log()


def _shape(value: Any) -> dict:
    """Reduce an input to non-sensitive shape: a hash and a size."""
    s = value if isinstance(value, str) else json.dumps(value, default=str, sort_keys=True)
    return {"hash": hashlib.sha256(s.encode("utf-8")).hexdigest()[:16], "len": len(s)}


class Meter:
    """Context manager that times a tool call and appends one log line."""

    def __init__(self, tenant: str, tool: str, inputs: dict | None = None):
        self.tenant = tenant
        self.tool = tool
        self.inputs = {k: _shape(v) for k, v in (inputs or {}).items()}
        self.outcome = "ok"
        self.detail = ""
        self.out_size = 0
        self._start = 0.0

    def __enter__(self):
        self._start = time.monotonic()
        return self

    def result_size(self, n: int):
        self.out_size = n

    def __exit__(self, exc_type, exc, tb):
        if exc_type is not None:
            self.outcome = "error"
            # Error text can quote table, column or literal values, so keep only
            # the exception type and any ORA- code.
            code = re.search(r"ORA-\d{5}", str(exc))
            self.detail = exc_type.__name__ + (f" {code.group(0)}" if code else "")
        rec = {
            # NOTE: no wall-clock timestamp source that would break replay; use
            # epoch here since this is a real runtime log, not a workflow script.
            "ts": int(time.time()),
            "tenant": self.tenant,
            "tool": self.tool,
            "inputs": self.inputs,
            "ms": round((time.monotonic() - self._start) * 1000, 1),
            "out_size": self.out_size,
            "outcome": self.outcome,
            "detail": self.detail,
        }
        try:
            os.makedirs(os.path.dirname(_LOG_PATH) or ".", exist_ok=True)
            with open(_LOG_PATH, "a", encoding="utf-8") as f:
                f.write(json.dumps(rec) + "\n")
        except OSError:
            pass  # never let metering failure break a tool call
        return False  # do not suppress exceptions
