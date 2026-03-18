# Predchain Python SDK v2

Direct-chain Python SDK v2 for Predchain.

This repo is meant to be used as the relayer-facing submission layer for an
orderbook or execution service. It talks directly to chain REST/RPC and does
not depend on the demo API.

Important behavior:

- it is fixed to the current Predchain chain id (`pmtest-1`)
- it does **not** sign orders
- it expects any settlement orders to already contain valid off-chain
  signatures
- it **does** sign the outer native Cosmos relayer tx with the configured
  relayer key

## The Main Idea

The normal entrypoint is:

- `PredchainRelayer` for one relayer key
- `PredchainRelayerPool` for multiple relayer keys

Those two classes are the relayer-shaped API. They are the surface that should
feel like “the relayer”.

The lower-level classes still exist:

- `PredchainSDKv2Client`
- `PredchainSDKv2Pool`

but those are now the escape hatch when you want the full raw tx surface or
direct broadcast-mode control.

## Installation

```bash
pip install .
```

Runtime dependencies:

- `protobuf`
- `coincurve`

## Single Relayer Quick Start

```python
from predchain_sdk_v2 import Order, PredchainRelayer

relayer = PredchainRelayer.connect(
    api_url="http://46.62.232.134:1317",
    rpc_url="http://46.62.232.134:26657",
    signer_address="0xRELAYER",
    private_key_hex="RELAYER_PRIVATE_KEY_HEX",
)

relayer.warm()

taker = Order(
    salt=1,
    maker="0xTAKER_MAKER",
    signer="0xTAKER_SIGNER",
    taker="",
    token_id="0xTOKEN_ID",
    maker_amount="1000000",
    taker_amount="500000",
    expiration=0,
    nonce=1,
    fee_rate_bps=100,
    side="BUY",
    signature_type="EOA",
    signature="0xTAKER_ORDER_SIGNATURE",
)

maker = Order(
    salt=2,
    maker="0xMAKER_MAKER",
    signer="0xMAKER_SIGNER",
    taker="",
    token_id="0xTOKEN_ID",
    maker_amount="500000",
    taker_amount="1000000",
    expiration=0,
    nonce=2,
    fee_rate_bps=100,
    side="SELL",
    signature_type="EOA",
    signature="0xMAKER_ORDER_SIGNATURE",
)

submission = relayer.submit_match_orders(
    taker_order=taker,
    maker_orders=[maker],
    taker_fill_amount="500000",
    maker_fill_amounts=["1000000"],
)

print(submission.tx_hash)
print(submission.status)
print(submission.accepted)
```

By default, the relayer facade submits with sync/checktx semantics:

- fast return
- immediate `tx_hash`
- immediate accept/reject signal
- no need to thread Cosmos broadcast mode strings through normal code

If you want inline commit confirmation:

```python
submission = relayer.submit_match_orders(
    taker_order=taker,
    maker_orders=[maker],
    taker_fill_amount="500000",
    maker_fill_amounts=["1000000"],
    wait_for_commit=True,
)
```

## Multiple Relayers

If one relayer key is not enough for your throughput target, use
`PredchainRelayerPool`.

```python
from predchain_sdk_v2 import PredchainRelayerPool, RelayerConfig

pool = PredchainRelayerPool.from_configs(
    [
        RelayerConfig(
            api_url="http://46.62.232.134:1317",
            rpc_url="http://46.62.232.134:26657",
            signer_address="0xRELAYER_1",
            private_key_hex="RELAYER_1_PRIVATE_KEY_HEX",
        ),
        RelayerConfig(
            api_url="http://46.62.232.134:1317",
            rpc_url="http://46.62.232.134:26657",
            signer_address="0xRELAYER_2",
            private_key_hex="RELAYER_2_PRIVATE_KEY_HEX",
        ),
    ]
)

pool.warm()

submission = pool.submit_match_orders(
    taker_order=taker,
    maker_orders=[maker],
    taker_fill_amount="500000",
    maker_fill_amounts=["1000000"],
)
```

The pool:

- keeps sequence handling isolated per relayer signer
- balances across relayers when no explicit signer is requested
- still lets you route to one exact relayer signer when needed

## What The Relayer API Covers

The high-level relayer classes cover the operational things a relayer does most
often:

- warm signer state before hot submission
- return relayer health / signer status
- submit `MsgMatchOrders`
- submit `MsgCancelOrders`
- submit `MsgInvalidateNonce`
- wait for one tx when the caller wants commit confirmation

That means your normal orderbook integration can stay small:

1. build/receive already-signed orders
2. call `submit_match_orders(...)`
3. inspect `TxSubmission`
4. optionally call `get_tx(...)` / `wait_for_tx(...)`

## Sequence Handling

The SDK handles normal Cosmos sequence management internally.

For one relayer signer, it:

- serializes submissions per client instance
- caches local next sequence
- refreshes signer state on mismatch
- retries safely when the mismatch is recoverable

That is why the normal recommendation is:

- one `PredchainRelayer` per relayer key
- or one `PredchainRelayerPool` across multiple relayer keys

Callers should not need to manually manage sequence values during normal use.

## Example Implementations

The repo now includes relayer-style examples, not just low-level snippets:

- [examples/submit_match_orders.py](/Users/valkvalue/IdeaProjects/testss/predchain-python-sdk-v2/examples/submit_match_orders.py)
  - smallest direct relayer submission example
- [examples/relayer_single_worker.py](/Users/valkvalue/IdeaProjects/testss/predchain-python-sdk-v2/examples/relayer_single_worker.py)
  - shows how an orderbook hands one ready settlement to one relayer
- [examples/relayer_pool_worker.py](/Users/valkvalue/IdeaProjects/testss/predchain-python-sdk-v2/examples/relayer_pool_worker.py)
  - shows multi-relayer fanout through one relayer abstraction

## Lower-Level Escape Hatch

If you need full raw tx surface, those classes still exist:

- `PredchainSDKv2Client`
- `PredchainSDKv2Pool`

Use them only when you intentionally want:

- direct broadcast-mode strings
- direct per-module helper methods
- lower-level native tx control

## Return Shape

Every submission method returns `TxSubmission`.

Important fields:

- `tx_hash`
- `accepted`
- `committed`
- `success`
- `status`
- `broadcast_code`, `broadcast_raw_log`
- `committed_code`, `committed_raw_log`
- `gas_wanted`, `gas_used`

## Documentation

- [docs/transactions.md](/Users/valkvalue/IdeaProjects/testss/predchain-python-sdk-v2/docs/transactions.md)

## Regenerating Protobuf Bindings

```bash
bash scripts/generate_protos.sh
```

## Package Layout

- `predchain_sdk_v2/relayer.py`: relayer-shaped high-level API
- `predchain_sdk_v2/client.py`: lower-level direct-chain client
- `predchain_sdk_v2/pool.py`: lower-level multi-relayer pool
- `predchain_sdk_v2/messages.py`: protobuf message builders
- `predchain_sdk_v2/models.py`: request/response dataclasses
- `predchain_sdk_v2/crypto.py`: relayer signing helpers
- `proto/`: copied proto sources used to generate the Python bindings
