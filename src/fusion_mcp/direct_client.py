"""Backend — talks to Fusion BIP straight from this host over SOAP.

Each function takes a FusionContext, so client.py dispatches to it with zero
change to server.py. Queries run through a temporary data model: login -> create -> run -> delete.
"""

from __future__ import annotations

import uuid

from . import builders, soap
from .context import FusionContext
from .errors import FusionToolError


def _login(ctx: FusionContext):
    """Return (base_url, user, pw, token)."""
    url, user, pw = ctx.fusion_login()
    return url, user, pw, soap.login(url, user, pw)


def query_fusion(ctx: FusionContext, sql: str, columns: list[str]) -> str:
    """Read-only SELECT via an ephemeral data model: create -> run -> delete."""
    url, user, pw, token = _login(ctx)
    xdm = builders.build_data_model_xml(sql, columns)
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
