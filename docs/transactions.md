# Predchain Python SDK v2 Transaction Reference

This document describes the SDK in the shape it is intended to be used:

- `PredchainRelayer` for one relayer key
- `PredchainRelayerPool` for multiple relayer keys

The lower-level classes still exist, but they are secondary:

- `PredchainSDKv2Client`
- `PredchainSDKv2Pool`

## Operational Model

The SDK is meant to sit where a relayer would sit.

The normal flow is:

1. your orderbook decides a settlement
2. the orderbook already has signed orders
3. it calls the relayer SDK
4. the SDK builds and signs the outer native Cosmos tx
5. the SDK returns `TxSubmission`

The SDK does **not**:

- sign orders
- decide matching logic
- replace your orderbook

It only takes the already-prepared settlement/admin/action payload and submits
it to chain in a relayer-safe way.

## Main Entry Points

### `PredchainRelayer.connect(...)`

Builds a high-level relayer instance from one relayer key.

Use this for the common case: one worker, one relayer signer.

```python
from predchain_sdk_v2 import PredchainRelayer

relayer = PredchainRelayer.connect(
    api_url="http://46.62.232.134:1317",
    rpc_url="http://46.62.232.134:26657",
    signer_address="0xRELAYER",
    private_key_hex="RELAYER_PRIVATE_KEY_HEX",
)
```

### `PredchainRelayerPool.from_configs(...)`

Builds a high-level multi-relayer abstraction.

Use this when one relayer key is not enough for throughput and you want the SDK
to handle routing across several relayer signers.

```python
from predchain_sdk_v2 import PredchainRelayerPool, RelayerConfig

pool = PredchainRelayerPool.from_configs([
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
])
```

## Warm-Up And Health

### `warm()`

Fetches signer account state and warms the local sequence cache.

Use this once before a hot submission loop.

```python
relayer.warm()
pool.warm()
```

### `health()`

Returns a relayer-oriented health snapshot.

For one relayer:

- current chain id
- latest height
- latest block time
- whether the node is catching up
- signer existence and sequence data

For a pool:

- one health snapshot per relayer
- relayer count

### `signer_status()` / `signer_statuses()`

Returns sequence-focused status useful for debugging or monitoring.

### `balances(address=None)`

Returns bank balances directly from chain REST.

This is useful when diagnosing relayer funding or signer state issues.

## The Main Submission Methods

### `submit_match_orders(...)`

The main settlement method.

This expects:

- `taker_order`
- `maker_orders`
- `taker_fill_amount`
- `maker_fill_amounts`

The orders must already be signed. The SDK does not sign them.

Default behavior:

- submit with sync/checktx semantics
- return quickly with tx hash + accept/reject signal

Optional:

- `wait_for_commit=True`

That switches to inline commit observation without exposing Cosmos broadcast
mode strings in the normal API.

Example:

```python
submission = relayer.submit_match_orders(
    taker_order=taker_order,
    maker_orders=maker_orders,
    taker_fill_amount=taker_fill_amount,
    maker_fill_amounts=maker_fill_amounts,
)
```

### `submit_cancel_orders(...)`

Submits `MsgCancelOrders`.

Use this when the relayer/execution service needs to cancel one or more order
hashes for a signer/principal pair.

### `submit_invalidate_nonce(...)`

Submits `MsgInvalidateNonce`.

Use this when the relayer/execution service wants to raise the minimum valid
nonce for one signer/principal pair.

### `submit_message(...)`

Submits one already-built protobuf message through the relayer abstraction.

Use this when you need a non-settlement native tx, but still want the relayer
surface:

- one boolean `wait_for_commit`
- relayer-managed sequence handling
- one structured `TxSubmission`

### `submit_messages(...)`

Same as above, but for multi-message txs.

## Waiting For One Tx

### `wait_for_tx(tx_hash, timeout_seconds=None)`

Polls RPC until the tx is observed in a block or the timeout expires.

Use this when:

- you submitted fast
- you got a `tx_hash`
- you want to check final execution later

### `get_tx(tx_hash)`

Fetches one tx from REST by hash.

This is useful when you only need the current chain view of one tx, without
running a wait loop.

## Sequence Handling

The SDK is expected to handle normal relayer sequence concerns by itself.

For one signer it:

- serializes submissions per client instance
- keeps a local next-sequence cache
- refreshes signer state on mismatch
- retries safe sequence mismatches automatically

That means callers normally should **not** manage sequence values manually.

### `reset_sequence_cache()`

This exists as an escape hatch, not a normal workflow.

Use it only if:

- the same relayer key was used by another process
- you intentionally want to discard the SDK’s local sequence cache

## Multiple Relayers

`PredchainRelayerPool` exists because one Cosmos signer still has one sequence.

If you want more parallel throughput than one relayer key can safely support,
the right approach is:

- more relayer keys
- one SDK-managed client per relayer key
- one pool routing across them

The pool:

- isolates sequence handling per signer
- routes to explicit signer when you pass one
- otherwise balances across relayers

## Return Shape

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

Typical statuses:

- `accepted`
- `broadcast_rejected`
- `commit_timeout`
- `committed_success`
- `committed_failure`

## Example Implementations In This Repo

These are the best place to see how the SDK is meant to be used:

- [examples/submit_match_orders.py](/Users/valkvalue/IdeaProjects/testss/predchain-python-sdk-v2/examples/submit_match_orders.py)
- [examples/relayer_single_worker.py](/Users/valkvalue/IdeaProjects/testss/predchain-python-sdk-v2/examples/relayer_single_worker.py)
- [examples/relayer_pool_worker.py](/Users/valkvalue/IdeaProjects/testss/predchain-python-sdk-v2/examples/relayer_pool_worker.py)

## Lower-Level Escape Hatch

If you need broader raw tx coverage, you can still drop down to:

- `PredchainSDKv2Client`
- `PredchainSDKv2Pool`

Those expose:

- direct broadcast modes
- all module helper methods
- lower-level tx assembly/submission control

That layer is still useful, but it is no longer the recommended front door for
normal relayer integration.
