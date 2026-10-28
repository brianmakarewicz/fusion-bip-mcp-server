"""Fusion BIP MCP Server — expose Oracle Fusion BIP operations as tools.

Talks to Fusion BI Publisher directly over token-based SOAP: a login envelope
returns a session token, and catalog/report calls carry that token.
"""

__version__ = "0.1.0"
