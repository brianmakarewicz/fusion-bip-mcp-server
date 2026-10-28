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

# Cap returned text so a huge result can't blow up the agent's context.
_MAX_CHARS = int(os.environ.get("FUSION_MCP_MAX_CHARS", "40000"))
_ROW_END = "</ROW>"


def _clip(text: str) -> str:
    """Cut an over-long result at a row boundary so it stays valid XML, and say so."""
    if len(text) <= _MAX_CHARS:
        return text
    total = text.count(_ROW_END)
    cut = text.rfind(_ROW_END, 0, _MAX_CHARS)
    if cut == -1:
        return (f"Result too large to return ({len(text)} characters for a single row). "
                "Select fewer or narrower columns.")
    kept = text[: cut + len(_ROW_END)]
    shown = kept.count(_ROW_END)
    return (kept + "\n</ROWSET>\n"
            f"<!-- TRUNCATED: showing {shown} of {total} rows. Add a WHERE clause, "
            "FETCH FIRST n ROWS ONLY, or fewer columns to see the rest. -->")


@mcp.tool()
def query_fusion(sql: str, fusion_user: str | None = None) -> str:
    """Run one SQL query against Oracle Fusion and return the rows as XML.

    Use this to answer questions from live Fusion data: write the SQL, run it,
    and read the rows back. Results look like
    <ROWSET><ROW><COLUMN_NAME>value</COLUMN_NAME>...</ROW></ROWSET>, with tags
    taken from the column names or aliases (give expressions an alias, e.g.
    COUNT(*) AS INVOICE_COUNT).

    Rules: exactly one SELECT (or WITH ... SELECT); no semicolons; limit the rows
    (WHERE, ROWNUM or FETCH FIRST n ROWS ONLY), because large results are cut off.

    If the query fails, the Oracle error comes back. To fix a wrong table or
    column name (ORA-00942, ORA-00904), look the names up with this same tool:
      - find tables and views: SELECT OBJECT_NAME, OBJECT_TYPE FROM ALL_OBJECTS
        WHERE OBJECT_NAME LIKE 'AP_INVOICE%' AND OBJECT_TYPE IN ('TABLE','VIEW')
      - list columns: SELECT COLUMN_NAME, DATA_TYPE FROM ALL_TAB_COLUMNS
        WHERE TABLE_NAME = 'AP_INVOICES_ALL' ORDER BY COLUMN_ID
    DBA_ views are not available. For what a table holds and how tables join,
    Oracle's "Tables and Views for Oracle Fusion Cloud" guides (Financials,
    Procurement, HCM, SCM, and so on) on docs.oracle.com describe every table and
    view. Then correct the SQL and run it again.

    Args:
        sql: One SELECT statement.
        fusion_user: Optional account name, only used when the server is set up
                     with a credential helper. Leave it out otherwise.
    """
    ctx = default_context(fusion_user)
    with Meter(ctx.tenant, "query_fusion", {"sql": sql}) as m:
        out = client.query_fusion(ctx, sql)
        m.result_size(len(out))
        return _clip(out)


def main() -> None:
    """Launch the server over stdio, or run `fusion-mcp setup | forget | --help`.

    Only stdio is offered: the server does no caller authentication, so it is
    meant to be started by a local MCP client, not exposed on a network port.
    """
    import sys
    if len(sys.argv) > 1:
        from .credentials import cli
        raise SystemExit(cli(sys.argv[1:]))
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
