"""MCP server exposing Fusion BIP operations.

Runs over stdio for local MCP clients (Claude Code / Desktop). Each tool is
registered with a description an agent can read, resolves a FusionContext for
credentials, and records one metadata-only line in the metering log.
"""

from __future__ import annotations

import os

from mcp.server.mcpserver import MCPServer

from . import client
from .context import default_context
from .metering import Meter

mcp = MCPServer("fusion-bip")

# Cap returned text so a huge report can't blow up the agent's context.
_MAX_CHARS = int(os.environ.get("FUSION_MCP_MAX_CHARS", "40000"))


def _clip(text: str) -> str:
    if len(text) > _MAX_CHARS:
        return text[:_MAX_CHARS] + f"\n...[truncated, {len(text)} chars total]"
    return text


@mcp.tool()
def query_fusion(sql: str, columns: list[str], fusion_user: str | None = None) -> str:
    """Run a read-only SELECT against Oracle Fusion and return the rows as XML.

    Args:
        sql: A single SELECT statement. No trailing semicolon. Add WHERE/ROWNUM
             to keep the result small — BIP serializes the whole set.
        columns: Output column aliases in SELECT order, upper-case identifiers.
                 Alias every column in the SQL to a simple upper-case name.
        fusion_user: Optional account name. Leave it out to use the account
                     the server was configured with.
    """
    ctx = default_context(fusion_user)
    with Meter(ctx.tenant, "query_fusion", {"sql": sql, "columns": columns}) as m:
        out = client.query_fusion(ctx, sql, columns)
        m.result_size(len(out))
        return _clip(out)


def main() -> None:
    """Launch the server, or run `fusion-mcp setup` / `fusion-mcp forget`.

    Transport is chosen by FUSION_MCP_TRANSPORT (stdio|http).
    """
    import sys
    if len(sys.argv) > 1:
        from .credentials import cli
        raise SystemExit(cli(sys.argv[1:]))
    transport = os.environ.get("FUSION_MCP_TRANSPORT", "stdio").lower()
    if transport in ("http", "streamable-http"):
        # Remote transport. Bind to localhost or put an authenticating proxy in
        # front; the server itself does no caller authentication.
        mcp.run(transport="streamable-http")
    else:
        mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
