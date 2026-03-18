from __future__ import annotations

import threading
from typing import Any, Callable

from .client import PredchainSDKv2Client
from .messages import normalize_address
from .models import AccountInfo, RelayerConfig


_SIGNER_KWARGS = (
    "signer_address",
    "submitter",
    "authority",
    "holder",
    "signer",
    "principal",
    "from_address",
)


class PredchainSDKv2Pool:
    """
    Multi-relayer wrapper around `PredchainSDKv2Client`.

    The pool keeps sequence handling isolated per relayer signer by delegating
    each submission to one concrete client instance. If the caller provides an
    explicit signer-like kwarg, the pool routes to that exact relayer. When no
    explicit signer is given, the pool balances across relayers by least
    in-flight submissions with round-robin tie-breaking.
    """

    def __init__(self, clients: list[PredchainSDKv2Client]) -> None:
        if not clients:
            raise ValueError("PredchainSDKv2Pool requires at least one client")
        signer_map: dict[str, int] = {}
        for index, client in enumerate(clients):
            signer = client.cfg.signer_address
            if signer in signer_map:
                raise ValueError(f"duplicate relayer signer in pool: {signer}")
            signer_map[signer] = index

        self._clients = list(clients)
        self._signer_map = signer_map
        self._inflight = [0 for _ in clients]
        self._next_index = 0
        self._lock = threading.Lock()

    @classmethod
    def from_configs(cls, configs: list[RelayerConfig]) -> "PredchainSDKv2Pool":
        clients = [
            PredchainSDKv2Client(
                api_url=config.api_url,
                rpc_url=config.rpc_url,
                signer_address=config.signer_address,
                private_key_hex=config.private_key_hex,
                timeout_seconds=config.timeout_seconds,
                default_broadcast_mode=config.default_broadcast_mode,
                default_commit_timeout_seconds=config.default_commit_timeout_seconds,
                max_sequence_retries=config.max_sequence_retries,
            )
            for config in configs
        ]
        return cls(clients)

    def __len__(self) -> int:
        return len(self._clients)

    def signer_addresses(self) -> list[str]:
        return [client.cfg.signer_address for client in self._clients]

    def sync_signer_state(self) -> list[AccountInfo]:
        return [client.sync_signer_state() for client in self._clients]

    def signer_statuses(self, refresh: bool = True) -> list[dict[str, Any]]:
        return [client.signer_status(refresh=refresh) for client in self._clients]

    def health(self) -> dict[str, Any]:
        return {
            "ok": True,
            "relayer_count": len(self._clients),
            "relayers": [client.health() for client in self._clients],
        }

    def reset_sequence_cache(self, signer_address: str | None = None) -> None:
        if signer_address is None:
            for client in self._clients:
                client.reset_sequence_cache()
            return
        client = self.client_for_signer(signer_address)
        client.reset_sequence_cache()

    def client_for_signer(self, signer_address: str) -> PredchainSDKv2Client:
        signer = normalize_address(signer_address)
        index = self._signer_map.get(signer)
        if index is None:
            raise ValueError(f"no relayer in pool matches signer {signer}")
        return self._clients[index]

    def __getattr__(self, name: str) -> Any:
        target = getattr(self._clients[0], name)
        if not callable(target):
            return target

        def pooled_call(*args: Any, **kwargs: Any) -> Any:
            index, client = self._acquire_client(kwargs)
            try:
                method: Callable[..., Any] = getattr(client, name)
                return method(*args, **kwargs)
            finally:
                self._release_client(index)

        return pooled_call

    def _acquire_client(self, kwargs: dict[str, Any]) -> tuple[int, PredchainSDKv2Client]:
        explicit_signer = self._explicit_signer(kwargs)
        with self._lock:
            if explicit_signer is not None:
                index = self._signer_map.get(explicit_signer)
                if index is None:
                    raise ValueError(f"no relayer in pool matches signer {explicit_signer}")
            else:
                lowest = min(self._inflight)
                count = len(self._clients)
                index = 0
                for offset in range(count):
                    candidate = (self._next_index + offset) % count
                    if self._inflight[candidate] == lowest:
                        index = candidate
                        self._next_index = (candidate + 1) % count
                        break
            self._inflight[index] += 1
            return index, self._clients[index]

    def _release_client(self, index: int) -> None:
        with self._lock:
            self._inflight[index] = max(0, self._inflight[index] - 1)

    def _explicit_signer(self, kwargs: dict[str, Any]) -> str | None:
        for key in _SIGNER_KWARGS:
            raw = kwargs.get(key)
            if raw is None:
                continue
            value = str(raw).strip()
            if value == "":
                continue
            return normalize_address(value)
        return None


PredchainRelayerPool = PredchainSDKv2Pool
