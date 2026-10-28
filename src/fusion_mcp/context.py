"""Execution context — where credentials are resolved.

Nothing is built in: no pod, no user, no password. The person who installs the
server supplies them in one of three ways, checked in this order:

1. A credential helper of your own (several accounts). Set FUSION_MCP_HELPER_DIR
   to the folder holding conn_helper.py, which defines
       get_fusion_url(pod) -> str
       get_fusion_user(name, pod) -> (username, password)
   FUSION_MCP_USER names the default account; FUSION_MCP_POD is passed as `pod`.
2. A saved connection from `fusion-mcp setup` (recommended): URL and username in a
   config file, password in the OS keychain.
3. Plaintext environment variables FUSION_URL, FUSION_USERNAME, FUSION_PASSWORD.
   These sit unencrypted in your MCP client's config, so the server refuses them
   unless FUSION_MCP_ACCEPT_PLAINTEXT_PASSWORD=yes confirms you accept that risk.
"""

from __future__ import annotations

import os
import sys
from dataclasses import dataclass

from . import credentials
from .errors import FusionToolError

_SETUP_HINT = ("Run `fusion-mcp setup` to save a connection (password kept in the OS "
               "keychain), or see the README for the other options.")


@dataclass(frozen=True)
class FusionContext:
    """Resolved targets for one tool call."""

    fusion_user: str | None = None   # account name; None means the configured default
    tenant: str = "local"            # caller identity recorded in the usage log

    def fusion_login(self):
        """Return (base_url, username, password) for this call."""
        helper_dir = os.environ.get("FUSION_MCP_HELPER_DIR")
        if helper_dir:
            if helper_dir not in sys.path:
                sys.path.insert(0, helper_dir)
            try:
                from conn_helper import get_fusion_url, get_fusion_user
            except ImportError as e:
                raise FusionToolError(f"Could not load conn_helper from {helper_dir}: {e}") from e
            name = self.fusion_user or os.environ.get("FUSION_MCP_USER")
            if not name:
                raise FusionToolError("No Fusion account named: set FUSION_MCP_USER "
                                      "or pass fusion_user on the call.")
            pod = os.environ.get("FUSION_MCP_POD")
            try:
                user, pwd = get_fusion_user(name, pod)
                url = get_fusion_url(pod)
            except Exception as e:  # report the helper's message, never its data
                raise FusionToolError(f"Credential helper failed for account {name!r}: "
                                      f"{type(e).__name__}: {e}") from e
            return url, user, pwd

        url = os.environ.get("FUSION_URL")
        user = os.environ.get("FUSION_USERNAME")
        pwd = os.environ.get("FUSION_PASSWORD")
        if pwd:
            if os.environ.get("FUSION_MCP_ACCEPT_PLAINTEXT_PASSWORD", "").lower() != "yes":
                raise FusionToolError(
                    "FUSION_PASSWORD is set, but a plaintext password in your MCP config is unsafe. "
                    "Run `fusion-mcp setup` to store it in the OS keychain instead, or set "
                    "FUSION_MCP_ACCEPT_PLAINTEXT_PASSWORD=yes to confirm you accept the risk.")
            if not (url and user):
                raise FusionToolError("FUSION_PASSWORD is set but FUSION_URL or FUSION_USERNAME is missing.")
        else:
            saved = credentials.load()
            if not saved:
                raise FusionToolError("Fusion connection is not configured. " + _SETUP_HINT)
            url, user, pwd = saved
        if self.fusion_user and self.fusion_user.lower() != user.lower():
            raise FusionToolError(
                f"Only the configured account is available ({user}); "
                f"fusion_user={self.fusion_user!r} was requested.")
        return url, user, pwd


def default_context(fusion_user: str | None = None) -> FusionContext:
    """Resolve the context for a call, with an optional per-call account name."""
    return FusionContext(fusion_user=fusion_user or None)
