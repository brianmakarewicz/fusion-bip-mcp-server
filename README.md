# Fusion BIP MCP Server

An [MCP](https://modelcontextprotocol.io) server that gives an AI agent safe, described access to **Oracle Fusion BI Publisher**. Instead of handing an agent raw credentials, you expose one scoped, read-only tool it can call to query Fusion, and the server talks to Fusion's BI Publisher SOAP service directly. No database and no middle tier to stand up.

This is a public, source-only mirror of the core server for people who want to read the code or point their own agent at their own Fusion instance.

## The tool

| Tool | What it does | Access |
|------|--------------|--------|
| `query_fusion` | Run a read-only SELECT against Oracle Fusion and return the rows | read |

Running reports, reading the catalog, and deploying reports and data models are not part of this public version. `query_fusion` creates a temporary data model in the user's own `/~user` folder, runs it, and deletes it straight away.

## How it fits together

```
AI agent (Claude Code, etc.)
      │  MCP (stdio)
      ▼
  server.py        registers the tool, meters usage
      │
  client.py ─────► direct_client.py ──► BI Publisher SOAP  ──►  Oracle Fusion
      │                                   (soap.py builds the envelopes,
  context.py                               builders.py shapes the .xdm)
  (credentials/targets)
```

- `server.py` — the MCP server; registers the tool and its description.
- `client.py` — the backend seam the server imports.
- `direct_client.py` — the query implemented against BI Publisher SOAP.
- `soap.py` / `builders.py` — envelope construction and building the temporary `.xdm`.
- `context.py` — where the Fusion pod and user credentials are resolved for a call. The defaults in this mirror are placeholders (`your-pod`, `bip_user`); wire in your own.
- `metering.py` — an append-only, metadata-only usage log.

## Running it locally

```bash
pip install -e ".[stdio]"    # installs the mcp runtime
# set your Fusion pod + user in context.py (or via environment) and register
# fusion-mcp with your MCP client (Claude Code / Desktop) over stdio.
```

## Notes

- This mirror is the **direct-over-SOAP** path only. Credential wiring is intentionally left as placeholders — it does not run as-is against any real instance until you supply your own Fusion pod and a user who can create a data model in their own BI Publisher folder.
- No credentials, tokens, or private endpoints are included.

## License

MIT — see [LICENSE](LICENSE).
