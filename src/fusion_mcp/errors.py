"""Shared error type for both backends (direct SOAP and ATP relay)."""


class FusionToolError(RuntimeError):
    """A tool-level failure, carrying the BIP fault message when one is present."""
