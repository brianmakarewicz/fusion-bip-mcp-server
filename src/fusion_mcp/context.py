"""Execution context — the credential-injection seam.

A FusionContext carries what a tool call needs to reach Fusion: the pod to hit
and the user to authenticate as. Credentials are resolved here and nowhere else,
so the rest of the server only ever passes a FusionContext around and never sees
a raw password.

This mirror resolves credentials from a local helper. The pod and user below are
placeholders — wire in your own, or supply them through the environment.
"""

from __future__ import annotations

import os
import sys
from dataclasses import dataclass

# Local credential lookup. This is the only coupling to the host machine; the
# helper reads your Fusion pod URL and user from wherever you keep them.
_WORKSPACE = os.environ.get("FUSION_MCP_WORKSPACE", os.path.expanduser("~/workspace"))
if _WORKSPACE not in sys.path:
    sys.path.insert(0, _WORKSPACE)


@dataclass(frozen=True)
class FusionContext:
    """Resolved credentials + targets for one tool call."""

    # Fusion side — resolved lazily so the pod/user can vary per call.
    fusion_pod: str = "your-pod"
    fusion_cred: str = "bip_user"       # must have the BIP Author role

    # Identity of the caller, recorded in the metering log.
    tenant: str = "local"

    def fusion_login(self):
        """Return (base_url, username, password) for the Fusion pod/user."""
        from conn_helper import get_fusion_url, get_fusion_user
        url = get_fusion_url(self.fusion_pod)
        user, pwd = get_fusion_user(self.fusion_cred, self.fusion_pod)
        return url, user, pwd


def default_context(fusion_cred: str | None = None) -> FusionContext:
    """Resolve the context for a call, with an optional per-call user override."""
    if fusion_cred:
        return FusionContext(fusion_cred=fusion_cred)
    return FusionContext()
