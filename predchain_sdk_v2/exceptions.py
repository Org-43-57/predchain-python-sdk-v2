from __future__ import annotations


class PredchainRelayerError(RuntimeError):
    """Base error for relayer SDK failures."""


class PredchainHTTPError(PredchainRelayerError):
    """HTTP transport or upstream API error."""

    def __init__(self, status_code: int, message: str, body: object | None = None) -> None:
        super().__init__(f"http {status_code}: {message}")
        self.status_code = status_code
        self.body = body


class SequenceMismatchError(PredchainRelayerError):
    """Raised internally when the chain rejects a tx for stale sequence."""


class CommitTimeoutError(PredchainRelayerError):
    """Raised when waiting for commit times out."""
