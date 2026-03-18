from __future__ import annotations

from typing import Any

from .client import PredchainSDKv2Client
from .messages import build_msg_cancel_orders, build_msg_invalidate_nonce, build_msg_match_orders, normalize_address
from .models import AccountInfo, Order, RelayerConfig, TxSubmission
from .pool import PredchainSDKv2Pool


def _broadcast_mode(wait_for_commit: bool) -> str:
    return "BROADCAST_MODE_BLOCK" if wait_for_commit else "BROADCAST_MODE_SYNC"


class PredchainRelayer:
    """
    High-level relayer facade over `PredchainSDKv2Client`.

    This is the intended day-to-day entrypoint when the SDK is being used as
    "the relayer" from an orderbook or execution service. It keeps the normal
    direct-chain behavior while hiding most broadcast-mode plumbing behind a
    relayer-shaped API.
    """

    def __init__(self, client: PredchainSDKv2Client) -> None:
        self._client = client

    @classmethod
    def connect(
        cls,
        api_url: str,
        rpc_url: str,
        signer_address: str,
        private_key_hex: str,
        timeout_seconds: float = 30.0,
        default_commit_timeout_seconds: float = 25.0,
        max_sequence_retries: int = 2,
    ) -> "PredchainRelayer":
        return cls(
            PredchainSDKv2Client(
                api_url=api_url,
                rpc_url=rpc_url,
                signer_address=signer_address,
                private_key_hex=private_key_hex,
                timeout_seconds=timeout_seconds,
                default_broadcast_mode="BROADCAST_MODE_SYNC",
                default_commit_timeout_seconds=default_commit_timeout_seconds,
                max_sequence_retries=max_sequence_retries,
            )
        )

    @classmethod
    def from_config(cls, config: RelayerConfig) -> "PredchainRelayer":
        return cls(
            PredchainSDKv2Client(
                api_url=config.api_url,
                rpc_url=config.rpc_url,
                signer_address=config.signer_address,
                private_key_hex=config.private_key_hex,
                timeout_seconds=config.timeout_seconds,
                default_broadcast_mode="BROADCAST_MODE_SYNC",
                default_commit_timeout_seconds=config.default_commit_timeout_seconds,
                max_sequence_retries=config.max_sequence_retries,
            )
        )

    @property
    def client(self) -> PredchainSDKv2Client:
        return self._client

    @property
    def signer_address(self) -> str:
        return self._client.cfg.signer_address

    def warm(self) -> AccountInfo:
        """Warm signer account/sequence cache before a hot submit loop."""
        return self._client.sync_signer_state()

    def health(self) -> dict[str, Any]:
        return self._client.health()

    def signer_status(self, refresh: bool = True) -> dict[str, Any]:
        return self._client.signer_status(refresh=refresh)

    def balances(self, address: str | None = None) -> dict[str, Any]:
        return self._client.balances(address=address)

    def get_tx(self, tx_hash: str) -> dict[str, Any]:
        return self._client.get_tx(tx_hash)

    def wait_for_tx(self, tx_hash: str, timeout_seconds: float | None = None) -> dict[str, Any]:
        return self._client.wait_for_tx(tx_hash, timeout_seconds=timeout_seconds)

    def reset_sequence_cache(self) -> None:
        self._client.reset_sequence_cache()

    def submit_message(
        self,
        message: Any,
        signer_address: str | None = None,
        gas_limit: int | None = None,
        wait_for_commit: bool = False,
        commit_timeout_seconds: float | None = None,
    ) -> TxSubmission:
        return self._client.submit_message(
            message=message,
            signer_address=signer_address,
            gas_limit=gas_limit,
            broadcast_mode=_broadcast_mode(wait_for_commit),
            commit_timeout_seconds=commit_timeout_seconds,
        )

    def submit_messages(
        self,
        messages: list[Any],
        signer_address: str | None = None,
        gas_limit: int | None = None,
        wait_for_commit: bool = False,
        commit_timeout_seconds: float | None = None,
    ) -> TxSubmission:
        return self._client.submit_messages(
            messages=messages,
            signer_address=signer_address,
            gas_limit=gas_limit,
            broadcast_mode=_broadcast_mode(wait_for_commit),
            commit_timeout_seconds=commit_timeout_seconds,
        )

    def submit_match_orders(
        self,
        taker_order: Order | dict[str, Any],
        maker_orders: list[Order | dict[str, Any]],
        taker_fill_amount: str,
        maker_fill_amounts: list[str],
        submitter: str | None = None,
        surplus_recipient: str = "",
        gas_limit: int | None = None,
        wait_for_commit: bool = False,
        commit_timeout_seconds: float | None = None,
    ) -> TxSubmission:
        msg = build_msg_match_orders(
            submitter or self.signer_address,
            taker_order,
            maker_orders,
            taker_fill_amount,
            maker_fill_amounts,
            surplus_recipient,
        )
        return self.submit_message(
            message=msg,
            signer_address=msg.submitter,
            gas_limit=gas_limit,
            wait_for_commit=wait_for_commit,
            commit_timeout_seconds=commit_timeout_seconds,
        )

    def submit_cancel_orders(
        self,
        order_hashes: list[str],
        signer: str | None = None,
        principal: str = "",
        gas_limit: int | None = None,
        wait_for_commit: bool = False,
        commit_timeout_seconds: float | None = None,
    ) -> TxSubmission:
        msg = build_msg_cancel_orders(signer or self.signer_address, order_hashes, principal)
        return self.submit_message(
            message=msg,
            signer_address=msg.signer,
            gas_limit=gas_limit,
            wait_for_commit=wait_for_commit,
            commit_timeout_seconds=commit_timeout_seconds,
        )

    def submit_invalidate_nonce(
        self,
        min_valid_nonce: int,
        signer: str | None = None,
        principal: str = "",
        gas_limit: int | None = None,
        wait_for_commit: bool = False,
        commit_timeout_seconds: float | None = None,
    ) -> TxSubmission:
        msg = build_msg_invalidate_nonce(signer or self.signer_address, min_valid_nonce, principal)
        return self.submit_message(
            message=msg,
            signer_address=msg.signer,
            gas_limit=gas_limit,
            wait_for_commit=wait_for_commit,
            commit_timeout_seconds=commit_timeout_seconds,
        )


class PredchainRelayerPool:
    """
    High-level multi-relayer facade over `PredchainSDKv2Pool`.

    Use this when one relayer key is not enough and the caller wants "one
    relayer" abstraction that can fan out safely across several signer keys.
    """

    def __init__(self, pool: PredchainSDKv2Pool) -> None:
        self._pool = pool

    @classmethod
    def from_clients(cls, clients: list[PredchainSDKv2Client]) -> "PredchainRelayerPool":
        return cls(PredchainSDKv2Pool(clients))

    @classmethod
    def from_configs(cls, configs: list[RelayerConfig]) -> "PredchainRelayerPool":
        return cls(PredchainSDKv2Pool.from_configs(configs))

    @property
    def pool(self) -> PredchainSDKv2Pool:
        return self._pool

    def signer_addresses(self) -> list[str]:
        return self._pool.signer_addresses()

    def warm(self) -> list[AccountInfo]:
        return self._pool.sync_signer_state()

    def health(self) -> dict[str, Any]:
        return self._pool.health()

    def signer_statuses(self, refresh: bool = True) -> list[dict[str, Any]]:
        return self._pool.signer_statuses(refresh=refresh)

    def reset_sequence_cache(self, signer_address: str | None = None) -> None:
        self._pool.reset_sequence_cache(signer_address=signer_address)

    def client_for_signer(self, signer_address: str) -> PredchainSDKv2Client:
        return self._pool.client_for_signer(signer_address)

    def submit_message(
        self,
        message: Any,
        signer_address: str | None = None,
        gas_limit: int | None = None,
        wait_for_commit: bool = False,
        commit_timeout_seconds: float | None = None,
    ) -> TxSubmission:
        return self._pool.submit_message(
            message=message,
            signer_address=signer_address,
            gas_limit=gas_limit,
            broadcast_mode=_broadcast_mode(wait_for_commit),
            commit_timeout_seconds=commit_timeout_seconds,
        )

    def submit_messages(
        self,
        messages: list[Any],
        signer_address: str | None = None,
        gas_limit: int | None = None,
        wait_for_commit: bool = False,
        commit_timeout_seconds: float | None = None,
    ) -> TxSubmission:
        return self._pool.submit_messages(
            messages=messages,
            signer_address=signer_address,
            gas_limit=gas_limit,
            broadcast_mode=_broadcast_mode(wait_for_commit),
            commit_timeout_seconds=commit_timeout_seconds,
        )

    def submit_match_orders(
        self,
        taker_order: Order | dict[str, Any],
        maker_orders: list[Order | dict[str, Any]],
        taker_fill_amount: str,
        maker_fill_amounts: list[str],
        submitter: str | None = None,
        surplus_recipient: str = "",
        gas_limit: int | None = None,
        wait_for_commit: bool = False,
        commit_timeout_seconds: float | None = None,
    ) -> TxSubmission:
        signer = normalize_address(submitter) if submitter else None
        msg = build_msg_match_orders(
            signer or self._pool.signer_addresses()[0],
            taker_order,
            maker_orders,
            taker_fill_amount,
            maker_fill_amounts,
            surplus_recipient,
        )
        return self.submit_message(
            message=msg,
            signer_address=msg.submitter,
            gas_limit=gas_limit,
            wait_for_commit=wait_for_commit,
            commit_timeout_seconds=commit_timeout_seconds,
        )

    def submit_cancel_orders(
        self,
        order_hashes: list[str],
        signer: str | None = None,
        principal: str = "",
        gas_limit: int | None = None,
        wait_for_commit: bool = False,
        commit_timeout_seconds: float | None = None,
    ) -> TxSubmission:
        signer_address = normalize_address(signer) if signer else None
        msg = build_msg_cancel_orders(signer_address or self._pool.signer_addresses()[0], order_hashes, principal)
        return self.submit_message(
            message=msg,
            signer_address=msg.signer,
            gas_limit=gas_limit,
            wait_for_commit=wait_for_commit,
            commit_timeout_seconds=commit_timeout_seconds,
        )

    def submit_invalidate_nonce(
        self,
        min_valid_nonce: int,
        signer: str | None = None,
        principal: str = "",
        gas_limit: int | None = None,
        wait_for_commit: bool = False,
        commit_timeout_seconds: float | None = None,
    ) -> TxSubmission:
        signer_address = normalize_address(signer) if signer else None
        msg = build_msg_invalidate_nonce(
            signer_address or self._pool.signer_addresses()[0],
            min_valid_nonce,
            principal,
        )
        return self.submit_message(
            message=msg,
            signer_address=msg.signer,
            gas_limit=gas_limit,
            wait_for_commit=wait_for_commit,
            commit_timeout_seconds=commit_timeout_seconds,
        )
