"""Shared error type for the server."""

from mcp.server.mcpserver.exceptions import ToolError


class FusionToolError(ToolError):
    """A tool-level failure, carrying the BIP fault message when one is present.

    Subclassing the MCP SDK's ToolError means this message reaches the agent (after
    the SDK's "Error executing tool query_fusion:" prefix); any other exception is
    reported as a bare "Error executing tool" with the details kept on the server.
    """


class SessionExpired(FusionToolError):
    """BI Publisher rejected the session token (expired or logged out)."""
