"""Shared error type for the server."""

from mcp.server.mcpserver.exceptions import ToolError


class FusionToolError(ToolError):
    """A tool-level failure, carrying the BIP fault message when one is present.

    Subclassing the MCP SDK's ToolError means the message reaches the agent as the
    tool's error text, instead of the SDK's generic "Error executing tool".
    """


class SessionExpired(FusionToolError):
    """BI Publisher rejected the session token (expired or logged out)."""
