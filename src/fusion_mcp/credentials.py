"""Saved connection: URL and username in a small config file, password in the OS keychain.

The password goes into the operating system's own credential store (Windows
Credential Manager, macOS Keychain, or the Linux Secret Service) through the
`keyring` package. It is never written to a file by this server.

    fusion-mcp setup    prompt for URL, username and password, test the login, save
    fusion-mcp forget   remove the saved connection and its keychain entry
"""

from __future__ import annotations

import getpass
import json
import os
import sys
from pathlib import Path

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


def setup() -> int:
    from . import soap  # local import: soap is not needed to load credentials

    kr = _keyring()
    print("Fusion BIP MCP server setup. The password is stored in your OS keychain, not in a file.")
    url = input("Fusion URL (e.g. https://<your-pod>.fa.<region>.oraclecloud.com): ").strip().rstrip("/")
    user = input("Fusion username: ").strip()
    pw = getpass.getpass("Fusion password (hidden): ")
    if not (url.startswith("https://") and user and pw):
        print("URL must start with https://, and username and password are required. Nothing saved.")
        return 1
    print("Testing the login...")
    try:
        soap.login(url, user, pw)
    except FusionToolError as e:
        print(f"Login failed: {e}\nNothing saved.")
        return 1
    kr.set_password(SERVICE, _key(url, user), pw)
    p = config_path()
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
    print("Removed the saved connection and its keychain entry.")
    return 0


def cli(argv: list[str]) -> int:
    try:
        if argv[0] == "setup":
            return setup()
        if argv[0] == "forget":
            return forget()
    except FusionToolError as e:
        print(e, file=sys.stderr)
        return 1
    print(f"Unknown command {argv[0]!r}. Use: fusion-mcp [setup | forget]", file=sys.stderr)
    return 2
