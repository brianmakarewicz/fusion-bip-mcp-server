"""Backend — talks to Fusion BIP straight from this host over SOAP.

Queries run through a temporary data model: create -> run -> delete. The BI
Publisher session token is reused across calls, so the password is sent only at
the first login and again when the token expires.
"""

from __future__ import annotations

import threading
import uuid

from . import builders, soap
from .context import FusionContext
from .errors import FusionToolError, SessionExpired

# (base_url, username) -> session token. Held in memory only, never written out.
_tokens: dict[tuple[str, str], str] = {}
_lock = threading.Lock()


def _token(ctx: FusionContext, fresh: bool = False) -> tuple[str, str, str]:
    """Return (base_url, user, token), logging in only when there is no live token."""
    url, user, pw = ctx.fusion_login()
    key = (url, user.lower())
    with _lock:
        if fresh or key not in _tokens:
            _tokens[key] = soap.login(url, user, pw)
        return url, user, _tokens[key]


def _run_query(url: str, user: str, token: str, xdm: str) -> str:
    folder = f"/~{user}"
    name = "MCPQ_" + uuid.uuid4().hex[:10]
    soap.create_object(url, token, folder, name, "xdm", xdm)
    try:
        return soap.decode_report_bytes(
            soap.run_data_model_in_session(url, token, f"{folder}/{name}.xdm"))
    finally:
        try:
            soap.delete_object(url, token, f"{folder}/{name}.xdm")
        except FusionToolError:
            pass  # best-effort cleanup; the query result already returned


def query_fusion(ctx: FusionContext, sql: str, columns: list[str]) -> str:
    """Run one SELECT. If the cached token has expired, log in again once and retry."""
    xdm = builders.build_data_model_xml(sql, columns)
    url, user, token = _token(ctx)
    try:
        return _run_query(url, user, token, xdm)
    except SessionExpired:
        url, user, token = _token(ctx, fresh=True)
        return _run_query(url, user, token, xdm)
