"""Backend dispatcher.

The tools talk to Fusion BI Publisher straight from this host over BIP SOAP
(no database, no relay). server.py imports this module only, so the transport
details stay in one place.
"""

from __future__ import annotations

from .errors import FusionToolError  # re-exported: server.py references client.FusionToolError
from . import direct_client as _impl

# Re-export the tool function from the backend.
query_fusion = _impl.query_fusion

__all__ = [
    "FusionToolError", "query_fusion",
]
