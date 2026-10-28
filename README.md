# Fusion BIP MCP Server

An [MCP](https://modelcontextprotocol.io) server that lets an AI agent run SQL queries against **Oracle Fusion** through BI Publisher. It has one tool, `query_fusion`, and talks to Fusion's BI Publisher SOAP service directly from your machine, so there is no database or middle tier to stand up.

## The tool

| Tool | What it does | Arguments |
|------|--------------|-----------|
| `query_fusion` | Runs one SELECT against Oracle Fusion and returns the rows as XML | `sql`, `columns`, optional `fusion_user` |

- `sql` is a single SELECT with no trailing semicolon. Alias every column to an upper-case name, for example `SELECT VENDOR_NAME AS SUPPLIER_NAME FROM POZ_SUPPLIERS_V WHERE ROWNUM <= 10`.
- `columns` lists those aliases in SELECT order, for example `["SUPPLIER_NAME"]`. BI Publisher needs them to map the output. A name that does not appear in the SQL is rejected before anything is sent to Fusion.
- `fusion_user` is only used with a credential helper (option B below). Leave it out to use the account you configured.

Errors from Fusion, such as `ORA-00942: table or view does not exist`, come back as tool errors with Fusion's message. Results longer than 40,000 characters are truncated; set `FUSION_MCP_MAX_CHARS` to change that.

Each query runs through a temporary data model created in the account's own BI Publisher folder (`/~username`) and deleted when the call ends, whether it succeeds or fails. BI Publisher itself rejects anything other than a query, but the server does not parse the SQL, so use an account with only the access you want the agent to have.

## Setup

The repo contains no Fusion addresses, users or passwords. You supply your own.

**Requirements:** Python 3.10 or later, and a Fusion account that can create data models in its own BI Publisher folder (the BI Publisher Data Model Developer or Author role).

```bash
git clone https://github.com/brianmakarewicz/fusion-bip-mcp-server
cd fusion-bip-mcp-server
python -m venv .venv
.venv/bin/pip install -e .          # Windows: .venv\Scripts\pip install -e .
```

This installs the `fusion-mcp` command.

### Option A (recommended): save the connection in your OS keychain

```bash
.venv/bin/fusion-mcp setup
```

It asks for the Fusion URL, username and password (typing is hidden), tests the login, and saves. The password goes into the operating system's credential store (Windows Credential Manager, macOS Keychain, or the Linux Secret Service), never into a file. The URL and username go into `fusion-mcp/config.json` under your user config folder. `fusion-mcp forget` removes both.

### Option B: several accounts, through your own credential helper

Write a `conn_helper.py` in a folder outside the repo that defines `get_fusion_url(pod)` and `get_fusion_user(name, pod)`, returning the URL and `(username, password)`. [examples/conn_helper_example.py](examples/conn_helper_example.py) keeps the passwords in the OS keychain and only the account names in a file. Then set:

| Variable | Value |
|----------|-------|
| `FUSION_MCP_HELPER_DIR` | The folder containing your `conn_helper.py` |
| `FUSION_MCP_USER` | The account name to use when a call does not name one |
| `FUSION_MCP_POD` | Optional; passed to your helper as `pod` |

With option B the agent can name any account your helper knows through `fusion_user`, so only give the helper accounts you are happy for the agent to use.

### Option C (not recommended): plaintext environment variables

`FUSION_URL`, `FUSION_USERNAME` and `FUSION_PASSWORD` work, but the password then sits unencrypted in your MCP client's config file, where anything that can read your files can read it. The server refuses `FUSION_PASSWORD` unless you also set `FUSION_MCP_ACCEPT_PLAINTEXT_PASSWORD=yes` to confirm you accept that risk.

### Logins and session tokens

The server logs in to BI Publisher once and reuses the session token for later queries. The password is sent only at that first login, and again only when Fusion reports that the token has expired, at which point the server logs in again from the same stored credentials and retries the query once. The token is kept in memory and never written to disk.

### Register it with your MCP client

After option A there is nothing to pass; just point the client at the command.

Claude Code:

```bash
claude mcp add fusion-bip -- /path/to/fusion-bip-mcp-server/.venv/bin/fusion-mcp
```

Claude Desktop (`claude_desktop_config.json`):

```json
{
  "mcpServers": {
    "fusion-bip": {
      "command": "/path/to/fusion-bip-mcp-server/.venv/bin/fusion-mcp"
    }
  }
}
```

On Windows the command is `.venv\Scripts\fusion-mcp.exe`. For option B, add the `FUSION_MCP_*` variables to the client's `env` settings.

### Usage log

Every call appends one line to `metering.jsonl` in the repo folder (set `FUSION_MCP_METER_LOG` to move it). It records the time, tool, duration, result size and outcome. It stores a hash and length of the SQL, not the SQL itself, and never stores result data.

## How it fits together

- `server.py`: the MCP server; registers the tool and its description.
- `client.py`: the backend the server imports.
- `direct_client.py`: the query, run against BI Publisher SOAP.
- `soap.py`: builds the SOAP requests and reads Fusion's responses and errors.
- `builders.py`: checks the column list and builds the temporary data model.
- `context.py`: finds your credentials (helper, saved connection, or environment).
- `credentials.py`: the `setup` and `forget` commands and the OS keychain storage.
- `metering.py`: the usage log.

## License

MIT. See [LICENSE](LICENSE).
