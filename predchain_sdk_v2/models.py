from __future__ import annotations

from dataclasses import asdict, dataclass, is_dataclass
from typing import Any, Literal


BroadcastMode = Literal[
    "BROADCAST_MODE_UNSPECIFIED",
    "BROADCAST_MODE_ASYNC",
    "BROADCAST_MODE_SYNC",
    "BROADCAST_MODE_BLOCK",
]

DEFAULT_CHAIN_ID = "pmtest-1"


def to_payload(value: Any) -> Any:
    if is_dataclass(value):
        return {key: to_payload(val) for key, val in asdict(value).items()}
    if isinstance(value, dict):
        return {key: to_payload(val) for key, val in value.items()}
    if isinstance(value, (list, tuple)):
        return [to_payload(item) for item in value]
    return value


@dataclass(slots=True)
class Coin:
    denom: str
    amount: str


@dataclass(slots=True)
class ParlayLeg:
    market_id: int
    required_outcome: str


@dataclass(slots=True)
class Order:
    salt: int
    maker: str
    signer: str
    token_id: str
    maker_amount: str
    taker_amount: str
    expiration: int
    nonce: int
    fee_rate_bps: int
    side: str
    signature_type: str = "EOA"
    taker: str = ""
    signature: str = ""


@dataclass(slots=True)
class ValidatorSlot:
    index: int
    name: str
    consensus_address: str
    power: int
    consensus_pub_key: bytes | str = b""


@dataclass(slots=True)
class AccountInfo:
    address: str
    account_number: int
    sequence: int
    exists: bool


@dataclass(slots=True)
class RelayerConfig:
    api_url: str
    rpc_url: str
    signer_address: str
    private_key_hex: str
    chain_id: str = DEFAULT_CHAIN_ID
    timeout_seconds: float = 30.0
    default_broadcast_mode: BroadcastMode = "BROADCAST_MODE_BLOCK"
    default_commit_timeout_seconds: float = 25.0
    max_sequence_retries: int = 2


@dataclass(slots=True)
class TxSubmission:
    tx_hash: str
    mode_requested: BroadcastMode
    mode_used: BroadcastMode
    accepted: bool
    committed: bool
    success: bool
    status: str
    broadcast_code: int
    broadcast_raw_log: str
    broadcast_height: int
    gas_wanted: int
    gas_used: int
    committed_code: int | None = None
    committed_raw_log: str | None = None
    committed_height: int | None = None
    raw_broadcast: dict[str, Any] | None = None
    raw_committed: dict[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        return to_payload(self)
