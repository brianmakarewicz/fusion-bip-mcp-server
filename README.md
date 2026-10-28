# Fusion BIP MCP Server

An [MCP](https://modelcontextprotocol.io) server that lets an AI agent answer questions from live **Oracle Fusion** data. You ask in plain English; the agent writes the SQL, runs it through this server, reads the rows back, and if the query fails it looks up the right tables and columns and tries again. The server has one tool, `query_fusion`, and talks to Fusion's BI Publisher SOAP service directly from your machine, so there is no database or middle tier to stand up.

## The tool

| Tool | What it does | Arguments |
|------|--------------|-----------|
| `query_fusion` | Runs one query against Oracle Fusion and returns the rows as XML | `sql`, optional `fusion_user` |

- `sql` is one `SELECT` (or `WITH ... SELECT`). Results come back as `<ROWSET><ROW><COLUMN_NAME>value</COLUMN_NAME>...</ROW></ROWSET>`, with tags taken from the column names or aliases, so give expressions an alias (`COUNT(*) AS INVOICE_COUNT`).
- `fusion_user` is only used with a credential helper (option B below). Leave it out otherwise.

**When a query fails**, the Oracle error comes back as the tool's error, for example `ORA-00942: table or view does not exist` or `ORA-00904: "VENDOR": invalid identifier`. The tool's description tells the agent how to recover: look tables up in `ALL_OBJECTS`, list columns from `ALL_TAB_COLUMNS` (both through this same tool), or read Oracle's *Tables and Views for Oracle Fusion Cloud* guides on docs.oracle.com, then correct the SQL and run it again. Many Fusion objects are synonyms, which have no rows in `ALL_TAB_COLUMNS`, so the description also tells the agent to follow a synonym to its view or table, to filter date-effective `_F`/`_M` tables on `SYSDATE`, and to decode code columns through `FND_LOOKUP_VALUES`. `DBA_` views are not available to Fusion users, and every answer is limited to the data the connected account can see.

**Limits:** results over 40,000 characters are cut at a whole row and end with a comment saying how many rows were shown (set `FUSION_MCP_MAX_CHARS` to change the limit). Queries run against BI Publisher's `ApplicationDB_FSCM` data source, which can read Financials, Procurement, SCM and HCM tables, subject to the account's data security.

**What it accepts:** the SQL must start with `SELECT` or `WITH` and must not contain a semicolon (one trailing semicolon is removed). The query runs inside a short PL/SQL block so BI Publisher can read the column names; refusing semicolons means nothing can be added after the query. BI Publisher also refuses DML and DDL on its own. Even so, use an account with only the access you want the agent to have.

Each query runs through a temporary data model created in the account's own BI Publisher folder (`/~username`) and deleted when the call ends, whether it succeeds or fails.

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

It asks for the Fusion URL (`https://<your-pod>.fa.<region>.oraclecloud.com`; a pasted Fusion page address is trimmed to that), the username and the password (typing is hidden), tests the login, and saves only if the login works. The password goes into the operating system's credential store (Windows Credential Manager, macOS Keychain, or the Linux Secret Service), never into a file. The URL and username go into `fusion-mcp/config.json` under your user config folder. `fusion-mcp forget` removes both (the usage log, if any, stays in the same folder). Running `setup` again replaces the saved connection.

The hidden password prompt needs a real console: run `setup` from PowerShell, cmd, Terminal or a Linux/macOS shell. In Git Bash (mintty) prefix it with `winpty`, or use `fusion-mcp setup --password-stdin` and pipe in three lines: the URL, the username, then the password. `fusion-mcp --help` lists the commands.

### Option B: several accounts, through your own credential helper

Write a `conn_helper.py` in a folder outside the repo that defines `get_fusion_url(pod)` and `get_fusion_user(name, pod)`, returning the URL and `(username, password)`. [examples/conn_helper_example.py](examples/conn_helper_example.py) keeps the passwords in the OS keychain and only the account names in a file. Then set:

| Variable | Value |
|----------|-------|
| `FUSION_MCP_HELPER_DIR` | The folder containing your `conn_helper.py` |
| `FUSION_MCP_USER` | The account name to use when a call does not name one |
| `FUSION_MCP_POD` | Optional; passed to your helper as `pod` |

Add an account with `.venv/bin/python conn_helper.py add <name>` (use the repo's virtual environment, which has `keyring`). Remove one by deleting it from `accounts.json` and its keychain entry (service `fusion-bip-mcp-server-helper`); `fusion-mcp forget` does not touch helper accounts.

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

Every call appends one line to `metering.jsonl` in the same `fusion-mcp` config folder (set `FUSION_MCP_METER_LOG` to move it). It records the time, tool, duration, result size and outcome; for errors it keeps only the error type and ORA- code. It stores a hash and length of the SQL, not the SQL itself, and never stores result data.

### Which credentials are used

The server checks in this order and uses the first that is set: a credential helper (`FUSION_MCP_HELPER_DIR`), then `FUSION_PASSWORD` (option C), then the saved connection from `fusion-mcp setup`. A leftover `FUSION_PASSWORD` therefore takes precedence over a saved connection.

If Fusion rejects the login, the server stops trying for five minutes so that an agent retrying in a loop cannot lock the account. Fix the credentials and restart the server.

The server runs over stdio only, started by your MCP client. It has no network listener and does no caller authentication of its own.

## How it fits together

- `server.py`: the MCP server; registers the tool and its description.
- `client.py`: the backend the server imports.
- `direct_client.py`: the query, run against BI Publisher SOAP.
- `soap.py`: builds the SOAP requests and reads Fusion's responses and errors.
- `builders.py`: checks the SQL and builds the temporary data model.
- `context.py`: finds your credentials (helper, saved connection, or environment).
- `credentials.py`: the `setup` and `forget` commands and the OS keychain storage.
- `metering.py`: the usage log.

## License

MIT. See [LICENSE](LICENSE).
