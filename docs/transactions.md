# Predchain Python SDK v2 Transaction Reference

This SDK should be understood as one unified relayer/query client.

Use these public names:

- `PredchainRelayerClient`
- `PredchainRelayerPool`

Those are the recommended names for integration, but they point to the same
underlying implementations as `PredchainSDKv2Client` and `PredchainSDKv2Pool`.

That means:

- one implementation
- no thin duplicate relayer wrapper
- query methods and submit methods live together on the same client

## Operational Model

The normal flow is:

1. your orderbook decides a settlement
2. the orderbook already has signed orders
3. it calls the relayer client
4. the client builds and signs the outer native Cosmos tx
5. the client returns `TxSubmission`

The SDK does **not**:

- sign orders
- decide matching logic
- replace your orderbook

It only takes already-prepared settlement/admin/action payloads and submits
them to chain in a relayer-safe way.

## Main Entry Points

### `PredchainRelayerClient(...)`

Use this for the common case: one worker, one relayer signer.

```python
from predchain_sdk_v2 import PredchainRelayerClient

relayer = PredchainRelayerClient(
    api_url="http://46.62.232.134:1317",
    rpc_url="http://46.62.232.134:26657",
    signer_address="0xRELAYER",
    private_key_hex="RELAYER_PRIVATE_KEY_HEX",
)
```

### `PredchainRelayerPool([...])`

Use this when one relayer key is not enough for throughput and you want one
SDK-managed pool across multiple relayer signers.

```python
from predchain_sdk_v2 import PredchainRelayerClient, PredchainRelayerPool

pool = PredchainRelayerPool([
    PredchainRelayerClient(... signer_address="0xRELAYER_1", private_key_hex="..."),
    PredchainRelayerClient(... signer_address="0xRELAYER_2", private_key_hex="..."),
])
```

## Query / Read Methods

The same relayer client also exposes the normal read methods a relayer needs:

### `status() -> dict`

Fetches raw CometBFT RPC `/status`.

### `health() -> dict`

Returns a relayer-oriented snapshot:

- chain id
- latest height
- latest block time
- whether the node is catching up
- signer existence / account number / sequence

### `get_account_info(address=None, refresh_sequence_cache=False) -> AccountInfo`

Fetches account number and sequence for the relayer signer or another account.

### `signer_status(refresh=True) -> dict`

Returns signer-focused status including the cached next sequence.

### `balances(address=None) -> dict`

Fetches bank balances from chain REST.

### `get_tx(tx_hash) -> dict`

Fetches one tx from chain REST by hash.

### `wait_for_tx(tx_hash, timeout_seconds=None) -> dict`

Polls RPC until the tx is observed in a block or the timeout expires.

## Submission Methods

All submission methods return `TxSubmission`.

Important fields:

- `tx_hash`
- `accepted`
- `committed`
- `success`
- `status`
- `broadcast_code`
- `broadcast_raw_log`
- `committed_code`
- `committed_raw_log`
- `gas_wanted`
- `gas_used`

### `submit_message(...)`

Low-level one-message submission path.

Use this when you already built a protobuf message yourself.

### `submit_messages(...)`

Low-level multi-message submission path.

### `match_orders(...)`

Main settlement method.

This expects:

- `taker_order`
- `maker_orders`
- `taker_fill_amount`
- `maker_fill_amounts`

The orders must already be signed. The SDK does not sign them.

Recommended hot-path usage:

```python
submission = relayer.match_orders(
    taker_order=taker_order,
    maker_orders=maker_orders,
    taker_fill_amount=taker_fill_amount,
    maker_fill_amounts=maker_fill_amounts,
    broadcast_mode="BROADCAST_MODE_SYNC",
)
```

### `cancel_orders(...)`

Submits `MsgCancelOrders`.

### `invalidate_nonce(...)`

Submits `MsgInvalidateNonce`.

### Other chain tx methods

The same client also includes the broader chain tx helpers:

- bank send
- market txs
- CTF txs
- settlement txs
- PoA admin txs
- testnet mint admin txs

## Sequence Handling

The SDK is expected to handle normal relayer sequence concerns by itself.

For one signer it:

- serializes submissions per client instance
- keeps a local next-sequence cache
- refreshes signer state on mismatch
- retries safe sequence mismatches automatically

That means callers normally should **not** manage sequence values manually.

### `sync_signer_state()`

Warm signer account/sequence state before a hot submit loop.

### `reset_sequence_cache()`

Escape hatch only.

Use it when:

- the same relayer key was used by another process
- you want the next submit to re-read chain state

## Multiple Relayers

`PredchainRelayerPool` exists because one Cosmos signer still has one sequence.

If you want more parallel throughput than one relayer key can safely support:

- use more relayer keys
- one SDK-managed client per key
- route through the pool

The pool:

- isolates sequence handling per signer
- routes to explicit signer when you pass one
- otherwise balances across relayers

The pool delegates the same tx/query methods as the single relayer client.

## Example Implementations In This Repo

- [examples/submit_match_orders.py](/Users/valkvalue/IdeaProjects/testss/predchain-python-sdk-v2/examples/submit_match_orders.py)
- [examples/relayer_single_worker.py](/Users/valkvalue/IdeaProjects/testss/predchain-python-sdk-v2/examples/relayer_single_worker.py)
- [examples/relayer_pool_worker.py](/Users/valkvalue/IdeaProjects/testss/predchain-python-sdk-v2/examples/relayer_pool_worker.py)
