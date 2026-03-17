# Predchain Python SDK v2

Direct-chain Python SDK v2 for Predchain.

This package is meant to be called by an orderbook or execution service when a
native chain transaction is ready to be submitted.

Important behavior:

- It talks directly to the chain REST/RPC endpoints.
- It does not depend on the demo API.
- It does not sign orders.
- It expects any settlement orders passed into `match_orders()` to already
  contain valid off-chain signatures.
- It does sign the native relayer transaction with the configured relayer key.

## What This SDK Is For

Use this SDK when you already have:

- a relayer private key
- already-signed order payloads
- a direct chain endpoint

and you need to:

- submit one chain tx
- get back the tx hash
- know whether the tx was accepted, committed, or failed

## Installation

```bash
pip install .
```

Runtime dependencies:

- `protobuf`
- `coincurve`

## Quick Start

```python
from predchain_sdk_v2 import Order, PredchainSDKv2Client

client = PredchainSDKv2Client(
    api_url="http://46.62.232.134:1317",
    rpc_url="http://46.62.232.134:26657",
    signer_address="0xrelayeraddress",
    private_key_hex="YOUR_RELAYER_PRIVATE_KEY_HEX",
)

taker = Order(
    salt=1,
    maker="0xmaker",
    signer="0xmaker",
    taker="",
    token_id="0xTOKEN",
    maker_amount="1000000",
    taker_amount="500000",
    expiration=0,
    nonce=1,
    fee_rate_bps=100,
    side="BUY",
    signature_type="EOA",
    signature="0xSIGNED_TAKER_ORDER_BYTES",
)

maker = Order(
    salt=2,
    maker="0xmaker2",
    signer="0xmaker2",
    taker="",
    token_id="0xTOKEN",
    maker_amount="500000",
    taker_amount="1000000",
    expiration=0,
    nonce=2,
    fee_rate_bps=100,
    side="SELL",
    signature_type="EOA",
    signature="0xSIGNED_MAKER_ORDER_BYTES",
)

submission = client.match_orders(
    taker_order=taker,
    maker_orders=[maker],
    taker_fill_amount="500000",
    maker_fill_amounts=["1000000"],
)

print(submission.tx_hash)
print(submission.status)
print(submission.success)
```

## Return Shape

Every tx submission method returns `TxSubmission`.

Key fields:

- `tx_hash`: chain tx hash
- `accepted`: whether broadcast/checktx accepted the tx
- `committed`: whether the tx was later observed in a block
- `success`: final success flag
- `status`: one of `accepted`, `broadcast_rejected`, `commit_timeout`,
  `committed_success`, `committed_failure`
- `broadcast_code`, `broadcast_raw_log`
- `committed_code`, `committed_raw_log`
- `gas_wanted`, `gas_used`

## Broadcast Modes

Supported modes:

- `BROADCAST_MODE_ASYNC`
- `BROADCAST_MODE_SYNC`
- `BROADCAST_MODE_BLOCK`

Behavior:

- `ASYNC`: returns after broadcast request
- `SYNC`: returns after broadcast/checktx result
- `BLOCK`: internally does sync broadcast, then polls RPC until the tx is
  committed or times out

## Sequence Handling

The SDK serializes submissions per client instance and maintains a local
sequence cache for the relayer signer. On a sequence mismatch it refreshes the
signer account and retries.

This helps with the normal Cosmos relayer nonce/sequence problem, but the
recommended production pattern is still:

- one queue per relayer key
- one `PredchainSDKv2Client` instance per relayer worker

## Modules Covered

The SDK currently supports:

- bank send
- testnet mint admin txs
- market txs
- CTF txs
- settlement txs
- PoA admin txs

See [docs/transactions.md](/Users/valkvalue/IdeaProjects/testss/predchain-python-sdk-v2/docs/transactions.md) for the method-by-method reference.

## Main API

Low-level helpers:

- `status()`
- `chain_id()`
- `get_account_info()`
- `get_tx()`
- `wait_for_tx()`
- `submit_message()`
- `broadcast_tx_bytes()`

High-level tx methods:

- `send()`
- `admin_mint_usdc()`
- `admin_burn_usdc()`
- `update_testnetmint_admin()`
- `create_market()`
- `create_parlay_market()`
- `create_neg_risk_group()`
- `update_market_admin()`
- `convert_neg_risk_position()`
- `collapse_parlay_position()`
- `pause_market()`
- `set_market_fee()`
- `resolve_market()`
- `split_position()`
- `merge_positions()`
- `redeem_positions()`
- `match_orders()`
- `cancel_orders()`
- `invalidate_nonce()`
- `approve_agent()`
- `revoke_agent()`
- `pause_settlement()`
- `set_matcher_authorization()`
- `set_validator_set()`
- `update_poa_admin()`

## Regenerating Protobuf Bindings

```bash
bash scripts/generate_protos.sh
```

## Package Layout

- `predchain_sdk_v2/client.py`: high-level direct-chain client
- `predchain_sdk_v2/messages.py`: protobuf message builders
- `predchain_sdk_v2/models.py`: request/response dataclasses
- `predchain_sdk_v2/crypto.py`: relayer signing helpers
- `proto/`: copied proto sources used to generate the Python bindings
