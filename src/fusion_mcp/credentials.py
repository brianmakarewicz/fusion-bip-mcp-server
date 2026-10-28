"""Saved connection: URL and username in a small config file, password in the OS keychain.

The password goes into the operating system's own credential store (Windows
Credential Manager, macOS Keychain, or the Linux Secret Service) through the
`keyring` package. It is never written to a file by this server.

    fusion-mcp setup                   prompt for URL, username and password, test, save
    fusion-mcp setup --password-stdin  read the password from standard input instead
    fusion-mcp forget                  remove the saved connection and its keychain entry
"""

from __future__ import annotations

import getpass
import json
import os
import sys
from pathlib import Path
from urllib.parse import urlsplit

from .errors import FusionToolError

SERVICE = "fusion-bip-mcp-server"


def config_path() -> Path:
    base = os.environ.get("APPDATA") if os.name == "nt" else None
    base = base or os.environ.get("XDG_CONFIG_HOME") or os.path.expanduser("~/.config")
    return Path(base) / "fusion-mcp" / "config.json"


def _keyring():
    try:
        import keyring
        from keyring.backends import fail
    except ImportError as e:
        raise FusionToolError("The keyring package is not installed; reinstall with pip install -e .") from e
    if isinstance(keyring.get_keyring(), fail.Keyring):
        raise FusionToolError(
            "No OS keychain is available on this machine, so the password cannot be stored safely. "
            "Use a credential helper (FUSION_MCP_HELPER_DIR) or the plaintext environment variables "
            "described in the README.")
    return keyring


USAGE = """Usage:
  fusion-mcp                          start the MCP server (your MCP client runs this)
  fusion-mcp setup                    save a Fusion connection; password goes to the OS keychain
  fusion-mcp setup --password-stdin   same, reading the password from standard input
  fusion-mcp forget                   remove the saved connection and its keychain entry
"""


def normalize_url(url: str) -> str:
    """Keep only scheme and host, so a pasted Fusion page address still works."""
    parts = urlsplit(url.strip())
    if parts.scheme != "https" or not parts.netloc:
        raise FusionToolError("The Fusion URL must start with https://, e.g. "
                              "https://<your-pod>.fa.<region>.oraclecloud.com")
    return f"https://{parts.netloc}"


def _key(url: str, user: str) -> str:
    return f"{url.rstrip('/')}|{user.lower()}"


def load() -> tuple[str, str, str] | None:
    """Return (url, username, password) from the saved connection, or None if none is saved."""
    p = config_path()
    if not p.exists():
        return None
    cfg = json.loads(p.read_text(encoding="utf-8"))
    url, user = cfg["url"], cfg["username"]
    pw = _keyring().get_password(SERVICE, _key(url, user))
    if not pw:
        raise FusionToolError(f"No password in the OS keychain for {user}; run `fusion-mcp setup` again.")
    return url, user, pw


def setup(password_stdin: bool = False) -> int:
    from . import soap  # local import: soap is not needed to load credentials

    kr = _keyring()
    print("Fusion BIP MCP server setup. The password is stored in your OS keychain, not in a file.")
    url = normalize_url(input("Fusion URL (e.g. https://<your-pod>.fa.<region>.oraclecloud.com): "))
    user = input("Fusion username: ").strip()
    if password_stdin:
        pw = sys.stdin.readline().rstrip("\r\n")
    elif not sys.stdin.isatty():
        print("No interactive console, so the hidden password prompt cannot work here (for example "
              "Git Bash/mintty or piped input). Run setup from PowerShell, cmd or Terminal, prefix it "
              "with `winpty` in Git Bash, or use --password-stdin.")
        return 1
    else:
        pw = getpass.getpass("Fusion password (hidden): ")
    if not (user and pw):
        print("Username and password are required. Nothing saved.")
        return 1
    print("Testing the login...")
    try:
        soap.login(url, user, pw)
    except FusionToolError as e:
        print(f"Login failed: {e}\nNothing saved.")
        return 1
    p = config_path()
    if p.exists():  # replacing an earlier connection: drop its keychain entry first
        old = json.loads(p.read_text(encoding="utf-8"))
        if _key(old["url"], old["username"]) != _key(url, user):
            try:
                kr.delete_password(SERVICE, _key(old["url"], old["username"]))
            except Exception:
                pass
    kr.set_password(SERVICE, _key(url, user), pw)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps({"url": url, "username": user}, indent=2), encoding="utf-8")
    print(f"Saved. URL and username: {p}. Password: OS keychain, service '{SERVICE}'.")
    return 0


def forget() -> int:
    p = config_path()
    if not p.exists():
        print("No saved connection.")
        return 0
    cfg = json.loads(p.read_text(encoding="utf-8"))
    try:
        _keyring().delete_password(SERVICE, _key(cfg["url"], cfg["username"]))
    except Exception:
        pass  # already gone from the keychain
    p.unlink()
    try:
        p.parent.rmdir()  # only succeeds if nothing else (e.g. the usage log) is left in it
    except OSError:
        pass
    print("Removed the saved connection and its keychain entry.")
    return 0


def cli(argv: list[str]) -> int:
    try:
        if argv[0] == "setup":
            return setup(password_stdin="--password-stdin" in argv[1:])
        if argv[0] == "forget":
            return forget()
    except FusionToolError as e:
        print(e, file=sys.stderr)
        return 1
    if argv[0] in ("-h", "--help", "help"):
        print(USAGE)
        return 0
    print(f"Unknown command {argv[0]!r}.\n{USAGE}", file=sys.stderr)
    return 2
