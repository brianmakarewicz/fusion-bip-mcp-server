# Fusion BIP MCP Server

An [MCP](https://modelcontextprotocol.io) server that lets an AI agent answer questions from live **Oracle Fusion** data. You ask in plain English; the agent writes the SQL, runs it through this server, reads the rows back, and if the query fails it looks up the right tables and columns and tries again. The server's main tool is `query_fusion`; it can hold several Fusion instances with several users each, and the agent picks the instance and user on every call. It talks to Fusion's BI Publisher SOAP service directly from your machine, so there is no database or middle tier to stand up.

## The tool

| Tool | What it does | Arguments |
|------|--------------|-----------|
| `query_fusion` | Runs one query against Oracle Fusion and returns the rows as XML | `sql`, optional `instance`, optional `fusion_user` |
| `list_fusion_connections` | Lists the saved instances, their URLs and users, and the defaults (never passwords) | none |

- `sql` is one `SELECT` (or `WITH ... SELECT`). Results come back as `<ROWSET><ROW><COLUMN_NAME>value</COLUMN_NAME>...</ROW></ROWSET>`, with tags taken from the column names or aliases, so give expressions an alias (`COUNT(*) AS INVOICE_COUNT`).
- `instance` names a saved instance (see setup below); left out, the default instance is used.
- `fusion_user` names a user saved on that instance; left out, the instance's default user is used.

One session can switch freely, for example querying client A as a finance user, then as an HCM user, then client B. The tool's description tells the agent that each instance is a separate environment and not to mix data between them unless asked.

**When a query fails**, the Oracle error comes back as the tool's error, for example `ORA-00942: table or view does not exist` or `ORA-00904: "VENDOR": invalid identifier`. The tool's description tells the agent how to recover: look tables up in `ALL_OBJECTS`, list columns from `ALL_TAB_COLUMNS` (both through this same tool), or read Oracle's *Tables and Views for Oracle Fusion Cloud* guides on docs.oracle.com, then correct the SQL and run it again. Many Fusion objects are synonyms, which have no rows in `ALL_TAB_COLUMNS`, so the description also tells the agent to follow a synonym to its view or table, to filter date-effective `_F`/`_M` tables on `SYSDATE`, and to decode code columns through `FND_LOOKUP_VALUES`. `DBA_` views are not available to Fusion users.

**Limits:** results over 40,000 characters are cut at a whole row and end with a comment saying how many rows were shown (set `FUSION_MCP_MAX_CHARS` to change the limit). Queries run against BI Publisher's `ApplicationDB_FSCM` data source, which can read Financials, Procurement, SCM and HCM tables. SQL against most Fusion base tables is **not** filtered by the account's data security the way Fusion pages are (two users with different data roles get the same rows), so only save accounts whose access you are comfortable giving the agent.

**What it accepts:** the SQL must start with `SELECT` or `WITH` and must not contain a semicolon (one trailing semicolon is removed). The query runs inside a short PL/SQL block so BI Publisher can read the column names; refusing semicolons means nothing can be added after the query. BI Publisher also refuses DML and DDL on its own. Even so, use an account with only the access you want the agent to have.

Each query runs through a temporary data model created in the account's own BI Publisher folder (`/~username`) and deleted when the call ends, whether it succeeds or fails.

## Setup

The repo contains no Fusion addresses, users or passwords. You supply your own.

### Quick setup: let Claude Code do it

Paste this into Claude Code:

> Install and set up the Fusion MCP server from https://github.com/brianmakarewicz/fusion-bip-mcp-server. Follow "Steps for an AI agent" in its README.

It asks for a name for the instance, the Fusion URL and your username. The password goes into a small window that opens on your screen, never into the chat. When it is done, close and reopen Claude Code and ask a question.

#### Steps for an AI agent

1. Check that Python 3.10+ and Git are installed and that `python -c "import tkinter"` works (the password window needs it). If anything is missing, tell the user how to install it and stop.
2. Clone the repo into the user's home folder (`%USERPROFILE%` on Windows), create the venv with `python -m venv .venv` inside it, and run `pip install -e .` with the venv's pip. If the folder already exists, run `git pull` there instead of cloning.
3. Ask the user for a short instance name (for example the client's name), the Fusion URL, and the Fusion username. Never ask for the password in chat.
4. Run `<repo>/.venv/Scripts/fusion-mcp setup --instance NAME --url URL --user USER` (`.venv/bin/fusion-mcp` on macOS and Linux) with a timeout of at least five minutes. With no terminal attached, a window opens for the user to type the password, so tell them to look for it. It prints `Saved` on success. If other instances were already saved, ask whether this one should be the default and, if so, run `fusion-mcp default --instance NAME`. On `Login failed`, tell the user and run it again only when they ask, so a wrong password is not retried into a locked account.
5. Register the server for the user: `claude mcp add fusion-bip --scope user -- <full path to fusion-mcp>` (`fusion-mcp.exe` on Windows). If `claude mcp list` already has a server named `fusion-bip`, ask the user before replacing it or pick another name. Confirm with `claude mcp get fusion-bip` that it shows Connected.
6. Tell the user to close and reopen Claude Code, then ask a question about their Fusion data.

To add another user or instance later, the user can ask Claude Code to do it, which is step 4 again with the new names.

### Setting it up yourself

**Requirements:** Python 3.10 or later, and a Fusion account that can create data models in its own BI Publisher folder (the BI Publisher Data Model Developer or Author role).

```bash
git clone https://github.com/brianmakarewicz/fusion-bip-mcp-server
cd fusion-bip-mcp-server
python -m venv .venv
.venv/bin/pip install -e .          # Windows: .venv\Scripts\pip install -e .
```

This installs the `fusion-mcp` command.

### Option A (recommended): save instances and users in your OS keychain

```bash
.venv/bin/fusion-mcp setup --instance clienta
```

It asks for the Fusion URL (`https://<your-pod>.fa.<region>.oraclecloud.com`; a pasted Fusion page address is trimmed to that), the username and the password (typing is hidden), tests the login, and saves only if the login works. The password goes into the operating system's credential store (Windows Credential Manager, macOS Keychain, or the Linux Secret Service), never into a file. The instance names, URLs and usernames go into `fusion-mcp/config.json` under your user config folder. Leave out `--instance` and the instance is called `default`.

| Command | What it does |
|---------|--------------|
| `fusion-mcp setup --instance clientb` | Adds another instance (asks for its URL) |
| `fusion-mcp setup --instance clienta --user hcm_reader` | Adds a user to an existing instance (no URL asked) |
| `fusion-mcp setup --instance clienta --user fin_reader` | For a user already saved, changes the password |
| `fusion-mcp list` | Shows instances, URLs, users and defaults; never passwords |
| `fusion-mcp default --instance clientb [--user carol]` | Chooses what a call uses when it names no instance or user |
| `fusion-mcp forget --instance clienta [--user hcm_reader]` | Removes a user, or a whole instance, and its keychain entries |
| `fusion-mcp forget --all` | Removes everything (the usage log, if any, stays) |

The first instance and user you add become the defaults. A running server reads the saved connections on every call, so a new instance, user or password is used by the next query without restarting your MCP client. `--url` and `--user` can be given as options, and `--password-stdin` reads the password from standard input, so setup can be scripted.

In a terminal, `setup` asks for the password with a hidden prompt. Where there is no terminal (an AI agent running the command, or Git Bash), it opens a small password window instead, which needs Python's tkinter (included with the python.org installers; `python3-tk` on Linux). You can also pipe the password in with `--password-stdin`. `fusion-mcp --help` lists the commands.

Every saved user can be used by the agent through `instance` and `fusion_user`, so save only accounts whose access you are happy for the agent to have. To keep one session to a single client, set `FUSION_MCP_INSTANCE` in that session's MCP config (for example a project-level `.mcp.json`); it then becomes that session's default instance, although the agent can still name others.

### Option B: several accounts, through your own credential helper

Use this if you already keep credentials in your own store. Write a `conn_helper.py` in a folder outside the repo that defines `get_fusion_url(pod)` and `get_fusion_user(name, pod)`, returning the URL and `(username, password)`. [examples/conn_helper_example.py](examples/conn_helper_example.py) keeps the passwords in the OS keychain and only the account names in a file. Then set:

| Variable | Value |
|----------|-------|
| `FUSION_MCP_HELPER_DIR` | The folder containing your `conn_helper.py` |
| `FUSION_MCP_USER` | The account name to use when a call does not name one |
| `FUSION_MCP_POD` | Optional; passed to your helper as `pod` when a call names no `instance` |

A call's `instance` is passed to your helper as `pod`, so a helper that understands several pods gives the same switching as option A.

Add an account with `.venv/bin/python conn_helper.py add <name>` (use the repo's virtual environment, which has `keyring`). Remove one by deleting it from `accounts.json` and its keychain entry (service `fusion-bip-mcp-server-helper`); `fusion-mcp forget` does not touch helper accounts.

With option B the agent can name any account your helper knows through `fusion_user` (and any pod through `instance`), so only give the helper accounts you are happy for the agent to use.

### Option C (not recommended): plaintext environment variables

`FUSION_URL`, `FUSION_USERNAME` and `FUSION_PASSWORD` work, but the password then sits unencrypted in your MCP client's config file, where anything that can read your files can read it. It holds one connection only, so `instance` cannot be used. The server refuses `FUSION_PASSWORD` unless you also set `FUSION_MCP_ACCEPT_PLAINTEXT_PASSWORD=yes` to confirm you accept that risk.

### Logins and session tokens

The server logs in to BI Publisher once and reuses the session token for later queries. The password is sent only at that first login, and again only when Fusion reports that the token has expired, at which point the server logs in again from the same stored credentials and retries the query once. The token is kept in memory and never written to disk.

### Register it with your MCP client

After option A there is nothing to pass; just point the client at the command. Optionally set `FUSION_MCP_INSTANCE` in its `env` to choose that client's default instance.

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

The server checks in this order and uses the first that is set: a credential helper (`FUSION_MCP_HELPER_DIR`), then `FUSION_PASSWORD` (option C), then the saved instances from `fusion-mcp setup`. A leftover `FUSION_PASSWORD` therefore takes precedence over saved instances.

If Fusion rejects a login, the server stops trying that user with the same password for five minutes, so that an agent retrying in a loop cannot lock the account. Update the password (`fusion-mcp setup --instance NAME --user NAME`) and the next call tries the new one; other instances and users are not affected.

The server runs over stdio only, started by your MCP client. It has no network listener and does no caller authentication of its own.

## How it fits together

- `server.py`: the MCP server; registers the tools and their descriptions.
- `client.py`: the backend the server imports.
- `direct_client.py`: the query, run against BI Publisher SOAP.
- `soap.py`: builds the SOAP requests and reads Fusion's responses and errors.
- `builders.py`: checks the SQL and builds the temporary data model.
- `context.py`: finds the credentials for a call (helper, saved instances, or environment).
- `credentials.py`: the saved instances and users, the `setup`, `list`, `default` and `forget` commands, and the OS keychain storage.
- `metering.py`: the usage log.

## License

MIT. See [LICENSE](LICENSE).
