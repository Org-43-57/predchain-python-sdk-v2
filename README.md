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

## Main API Surface

The intended public names are:

- `PredchainRelayerClient`
- `PredchainRelayerPool`

These are not separate wrapper engines. They are the same underlying
implementations as:

- `PredchainSDKv2Client`
- `PredchainSDKv2Pool`

That is intentional now: one implementation, one set of query methods, one set
of submit methods, no thin duplicate facade layer.

Use the relayer names in normal integrations.

## Installation

```bash
pip install .
```

Runtime dependencies:

- `protobuf`
- `coincurve`

## Single Relayer Quick Start

```python
from predchain_sdk_v2 import Order, PredchainRelayerClient

relayer = PredchainRelayerClient(
    api_url="http://46.62.232.134:1317",
    rpc_url="http://46.62.232.134:26657",
    signer_address="0xRELAYER",
    private_key_hex="RELAYER_PRIVATE_KEY_HEX",
)

relayer.sync_signer_state()

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

submission = relayer.match_orders(
    taker_order=taker,
    maker_orders=[maker],
    taker_fill_amount="500000",
    maker_fill_amounts=["1000000"],
    broadcast_mode="BROADCAST_MODE_SYNC",
)

print(submission.tx_hash)
print(submission.status)
print(submission.accepted)
```

## Multiple Relayers

If one relayer key is not enough for your throughput target, use
`PredchainRelayerPool`.

```python
from predchain_sdk_v2 import PredchainRelayerClient, PredchainRelayerPool

pool = PredchainRelayerPool([
    PredchainRelayerClient(
        api_url="http://46.62.232.134:1317",
        rpc_url="http://46.62.232.134:26657",
        signer_address="0xRELAYER_1",
        private_key_hex="RELAYER_1_PRIVATE_KEY_HEX",
    ),
    PredchainRelayerClient(
        api_url="http://46.62.232.134:1317",
        rpc_url="http://46.62.232.134:26657",
        signer_address="0xRELAYER_2",
        private_key_hex="RELAYER_2_PRIVATE_KEY_HEX",
    ),
])

pool.sync_signer_state()

submission = pool.match_orders(
    taker_order=taker,
    maker_orders=[maker],
    taker_fill_amount="500000",
    maker_fill_amounts=["1000000"],
    broadcast_mode="BROADCAST_MODE_SYNC",
)
```

The pool:

- keeps sequence handling isolated per relayer signer
- balances across relayers when no explicit signer is requested
- still lets you route to one exact relayer signer when needed

## Queries And Status

This SDK is not only for submission. The relayer client also includes the
basic query/status methods a relayer normally needs:

- `status()`
- `health()`
- `get_account_info()`
- `signer_status()`
- `balances()`
- `get_tx()`
- `wait_for_tx()`

So the same client instance can:

- check signer/account state
- submit txs
- inspect tx status later

## Sequence Handling

The SDK handles normal Cosmos sequence management internally.

For one relayer signer, it:

- serializes submissions per client instance
- caches local next sequence
- refreshes signer state on mismatch
- retries safely when the mismatch is recoverable

That is why the normal recommendation is:

- one `PredchainRelayerClient` per relayer key
- or one `PredchainRelayerPool` across multiple relayer keys

Callers should not need to manually manage sequence values during normal use.

## Example Implementations

The repo includes relayer-style examples:

- [examples/submit_match_orders.py](/Users/valkvalue/IdeaProjects/testss/predchain-python-sdk-v2/examples/submit_match_orders.py)
  - smallest direct relayer submission example
- [examples/relayer_single_worker.py](/Users/valkvalue/IdeaProjects/testss/predchain-python-sdk-v2/examples/relayer_single_worker.py)
  - shows how an orderbook hands one ready settlement to one relayer
- [examples/relayer_pool_worker.py](/Users/valkvalue/IdeaProjects/testss/predchain-python-sdk-v2/examples/relayer_pool_worker.py)
  - shows multi-relayer fanout through one relayer abstraction

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

- `predchain_sdk_v2/client.py`: unified direct-chain relayer/query client
- `predchain_sdk_v2/pool.py`: multi-relayer pool
- `predchain_sdk_v2/messages.py`: protobuf message builders
- `predchain_sdk_v2/models.py`: request/response dataclasses
- `predchain_sdk_v2/crypto.py`: relayer signing helpers
- `proto/`: copied proto sources used to generate the Python bindings
