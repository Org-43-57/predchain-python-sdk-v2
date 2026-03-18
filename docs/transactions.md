# Predchain Python SDK v2 Transaction Reference

This document is the operational reference for
`predchain_sdk_v2.PredchainSDKv2Client`.

The goal of this SDK is not to sign orders or act like a demo helper. The goal
is to be the direct-chain submission layer a relayer or orderbook worker can
call when a native transaction is ready.

## Core Model

What this SDK does:

- fetches chain metadata and signer account state
- builds native Cosmos protobuf txs
- signs the outer relayer tx with the configured relayer key
- broadcasts to chain REST
- optionally waits for final commit through RPC
- returns a structured `TxSubmission`

What this SDK does not do:

- it does not sign settlement orders
- it does not run an orderbook
- it does not decide matching logic
- it does not replace relayer worker orchestration

For settlement specifically:

- `match_orders()` expects already-signed orders
- order signatures must already be present inside `taker_order` and
  `maker_orders`
- the SDK only signs the outer `MsgMatchOrders` tx as the relayer `submitter`

## Recommended Relayer Pattern

Use one client instance per relayer key.

Recommended worker shape:

1. create one `PredchainSDKv2Client`
2. call `sync_signer_state()` once at startup
3. submit with `BROADCAST_MODE_SYNC` for hot-path relaying
4. keep one serialized queue per relayer key
5. shard across multiple relayer keys if you need parallel throughput

Why:

- Cosmos sequence handling is per signer account
- one relayer key should not have concurrent uncontrolled writers
- this SDK already serializes submits per client instance, so normal callers do
  not need to manage sequence values manually

If you want multiple relayers inside one SDK abstraction, use
`PredchainSDKv2Pool`.

## Common Return Object

Every tx submission method returns `TxSubmission`.

Important fields:

- `tx_hash`: final chain tx hash
- `accepted`: whether the broadcast/checktx phase accepted the tx
- `committed`: whether the tx was later observed in a block
- `success`: final success flag
- `status`: high-level state string
- `broadcast_code`, `broadcast_raw_log`
- `committed_code`, `committed_raw_log`
- `gas_wanted`, `gas_used`
- `raw_broadcast`, `raw_committed`

Typical status meanings:

- `accepted`: broadcast accepted, no commit wait requested
- `broadcast_rejected`: rejected before commit
- `commit_timeout`: accepted, but not observed in time
- `committed_success`: committed with code `0`
- `committed_failure`: committed but failed during execution

## Broadcast Modes

### `BROADCAST_MODE_ASYNC`

Use when you only want the tx hash / immediate upstream response.

Pros:

- lowest latency
- minimal waiting

Tradeoff:

- no checktx confidence
- no commit confirmation inline

### `BROADCAST_MODE_SYNC`

Recommended default for hot relayer workers.

Pros:

- returns quickly
- still tells you whether the tx was accepted by broadcast/checktx
- gives immediate `tx_hash`

Tradeoff:

- final execution result is not inline

### `BROADCAST_MODE_BLOCK`

Use when you want inline finality for one operation.

Pros:

- returns commit outcome directly

Tradeoff:

- slower
- ties your caller to commit latency

## Relayer Health / Readiness Methods

### `status() -> dict`

Fetches raw CometBFT RPC `/status`.

Use this when you want the raw node status payload.

```python
client.status()
```

### `health() -> dict`

Returns a relayer-oriented snapshot:

- `chain_id`
- `latest_height`
- `latest_block_time`
- `catching_up`
- validator address from RPC
- signer presence / account number / sequence

Use this for monitoring or startup checks.

```python
client.health()
```

### `chain_id() -> str`

Returns the fixed Predchain chain id used by this SDK.

This SDK is intentionally single-chain for now, so callers do not need to
configure or refresh chain id dynamically.

```python
client.chain_id()
```

### `get_account_info(address: str | None = None, refresh_sequence_cache: bool = False) -> AccountInfo`

Fetches:

- `account_number`
- `sequence`
- account existence

Use this when you want exact signer/account metadata from chain state.

```python
client.get_account_info()
client.get_account_info("0x...")
```

### `signer_status(refresh: bool = True) -> dict`

Returns signer-focused info:

- signer address
- whether it exists
- chain `account_number`
- current chain sequence
- local cached next sequence
- current `chain_id`

Use this when debugging relayer nonce/sequence state.

```python
client.signer_status()
```

### `sync_signer_state() -> AccountInfo`

Warm-up method for hot relayer workers.

What it does:

- fetches signer account state
- fills local sequence cache

Use this once before starting a hot submit loop.

```python
client.sync_signer_state()
```

### `reset_sequence_cache() -> None`

Drops the local cached sequence state.

Normal callers usually do not need this. The SDK already uses it internally
after ambiguous transport failures.

Use this manually only when:

- you suspect out-of-band relayer submissions happened
- another service used the same relayer key
- you want the next submit to re-read chain state

```python
client.reset_sequence_cache()
```

## Multi-Relayer Pool

### `PredchainSDKv2Pool(clients: list[PredchainSDKv2Client])`

Wraps multiple relayer clients under one abstraction.

What it does:

- keeps sequence handling isolated per relayer signer
- balances new work across clients when no explicit signer is requested
- routes to one exact relayer when you pass a signer-like kwarg such as
  `submitter`, `authority`, `holder`, `signer`, or `signer_address`

Example:

```python
from predchain_sdk_v2 import PredchainSDKv2Client, PredchainSDKv2Pool

pool = PredchainSDKv2Pool([
    PredchainSDKv2Client(... signer_address="0xrelayer1", private_key_hex="..."),
    PredchainSDKv2Client(... signer_address="0xrelayer2", private_key_hex="..."),
])

pool.sync_signer_state()

submission = pool.match_orders(
    taker_order=taker_order,
    maker_orders=maker_orders,
    taker_fill_amount=taker_fill_amount,
    maker_fill_amounts=maker_fill_amounts,
    broadcast_mode="BROADCAST_MODE_SYNC",
)
```

### `PredchainSDKv2Pool.from_configs(configs: list[RelayerConfig])`

Builds a pool directly from multiple relayer configs.

### `signer_addresses() -> list[str]`

Returns the relayer signer addresses currently in the pool.

### `sync_signer_state() -> list[AccountInfo]`

Warms the signer account/sequence cache for every relayer in the pool.

### `signer_statuses(refresh: bool = True) -> list[dict]`

Returns signer status data for every relayer in the pool.

### `health() -> dict`

Returns one aggregated health snapshot containing all relayers.

### `reset_sequence_cache(signer_address: str | None = None) -> None`

Resets one relayer cache or all relayer caches in the pool.

### Delegated tx methods

The pool delegates the same tx submission methods as `PredchainSDKv2Client`,
including:

- `submit_message()`
- `submit_messages()`
- `match_orders()`
- `cancel_orders()`
- all admin, market, CTF, and settlement helpers

When no explicit relayer signer is provided, the pool picks the relayer with
the lowest current in-flight load, with round-robin tie-breaking.

### `balances(address: str | None = None) -> dict`

Fetches direct chain bank balances for an address.

Defaults to the relayer signer address.

```python
client.balances()
client.balances("0x...")
```

### `get_tx(tx_hash: str) -> dict`

Fetches one tx from chain REST by hash.

```python
client.get_tx("ABC123...")
```

### `wait_for_tx(tx_hash: str, timeout_seconds: float | None = None) -> dict`

Polls RPC `/tx` until the tx is observed or times out.

Use this if you submitted in `SYNC` mode and want to resolve finality later.

```python
client.wait_for_tx(tx_hash)
```

## Low-Level Submission Methods

### `submit_message(message, signer_address=None, gas_limit=None, broadcast_mode=None, commit_timeout_seconds=None) -> TxSubmission`

Generic submission path for one already-built protobuf message.

Use this when:

- you built a message outside the high-level helpers
- you want the SDK to do only the signer / tx / broadcast work

Fields:

- `message`: protobuf message instance
- `signer_address`: optional explicit signer, must match configured relayer
- `gas_limit`: optional override
- `broadcast_mode`: optional mode override
- `commit_timeout_seconds`: optional timeout for block mode

### `submit_messages(messages, signer_address=None, gas_limit=None, broadcast_mode=None, commit_timeout_seconds=None) -> TxSubmission`

Builds one native tx containing multiple protobuf messages.

Use this when:

- the relayer wants to submit one combined tx
- you have multiple compatible messages for one signer

Behavior:

- uses the sum of default gas limits unless you override `gas_limit`
- signs only once
- returns one `TxSubmission`

### `broadcast_tx_bytes(tx_bytes: bytes, mode=None) -> dict`

Broadcasts already-built tx bytes directly.

Use this when:

- some external component built and signed the tx already
- you only want the SDK’s HTTP transport path

## High-Level Chain Methods

All methods below:

- build the protobuf message for you
- enforce the configured relayer signer
- use sensible default gas limits
- return `TxSubmission`

## Bank

### `send(to_address, amount, denom="uusdc", from_address=None, gas_limit=None, broadcast_mode=None)`

Submits `cosmos.bank.v1beta1.MsgSend`.

Fields:

- `to_address`: recipient `0x...`
- `amount`: one string amount or a list of `Coin`
- `denom`: used when `amount` is a single string
- `from_address`: optional explicit sender, defaults to relayer signer
- `gas_limit`, `broadcast_mode`: optional overrides

```python
client.send(
    to_address="0x...",
    amount="1000000",
    denom="uusdc",
    broadcast_mode="BROADCAST_MODE_SYNC",
)
```

## Testnet Mint Admin

### `admin_mint_usdc(to, amount, authority=None, gas_limit=None, broadcast_mode=None)`

Submits `predictionmarket.testnetmint.v1.MsgAdminMintUSDC`.

Use this for testnet collateral minting.

### `admin_burn_usdc(from_address, amount, authority=None, gas_limit=None, broadcast_mode=None)`

Submits `predictionmarket.testnetmint.v1.MsgAdminBurnUSDC`.

### `update_testnetmint_admin(new_admin, authority=None, gas_limit=None, broadcast_mode=None)`

Rotates the testnet mint module admin.

## Market

### `create_market(question, taker_fee_bps=100, metadata_uri="", authority=None, gas_limit=None, broadcast_mode=None)`

Creates one binary market.

Fields:

- `question`
- `taker_fee_bps`
- `metadata_uri`
- optional `authority`

### `create_parlay_market(question, legs, taker_fee_bps=100, metadata_uri="", authority=None, gas_limit=None, broadcast_mode=None)`

Creates one parlay market.

Fields:

- `question`
- `legs`: list of `ParlayLeg`
- `taker_fee_bps`
- `metadata_uri`

### `create_neg_risk_group(title, market_ids, metadata_uri="", authority=None, gas_limit=None, broadcast_mode=None)`

Creates one neg-risk group.

Fields:

- `title`: display title for the group
- `market_ids`: initial member markets
- `metadata_uri`: optional metadata pointer
- optional `authority`: explicit admin signer override

### `update_neg_risk_group(group_id, add_market_ids=None, title="", metadata_uri="", authority=None, gas_limit=None, broadcast_mode=None)`

Appends new markets to one existing neg-risk group and optionally updates its title or metadata URI.

Fields:

- `group_id`: existing neg-risk group to update
- `add_market_ids`: optional new markets to append to the group
- `title`: optional replacement title when non-empty
- `metadata_uri`: optional replacement metadata URI when non-empty
- optional `authority`: explicit admin signer override

### `update_market_admin(new_admin, authority=None, gas_limit=None, broadcast_mode=None)`

Rotates the market module admin.

### `convert_neg_risk_position(group_id, anchor_market_id, amount, direction, holder=None, gas_limit=None, broadcast_mode=None)`

Converts within a neg-risk group.

### `collapse_parlay_position(parlay_market_id, amount, holder=None, gas_limit=None, broadcast_mode=None)`

Collapses a parlay position back into the target underlying position.

### `pause_market(market_id, paused, authority=None, gas_limit=None, broadcast_mode=None)`

Pauses or unpauses one market.

### `set_market_fee(market_id, taker_fee_bps, authority=None, gas_limit=None, broadcast_mode=None)`

Updates one market fee.

### `resolve_market(market_id, winning_outcome, resolution_metadata_uri="", authority=None, gas_limit=None, broadcast_mode=None)`

Resolves one market.

## CTF

### `split_position(condition_id, amount, partition, collateral_denom="uusdc", parent_collection_id="0", holder=None, gas_limit=None, broadcast_mode=None)`

Splits collateral into conditional positions.

Fields:

- `condition_id`
- `amount`
- `partition`
- `collateral_denom`
- `parent_collection_id`
- optional `holder`

### `merge_positions(condition_id, amount, partition, collateral_denom="uusdc", parent_collection_id="0", holder=None, gas_limit=None, broadcast_mode=None)`

Merges sibling positions back into collateral.

### `redeem_positions(condition_id, index_sets, collateral_denom="uusdc", parent_collection_id="0", holder=None, gas_limit=None, broadcast_mode=None)`

Redeems winning positions into collateral.

## Settlement

### `match_orders(taker_order, maker_orders, taker_fill_amount, maker_fill_amounts, submitter=None, surplus_recipient="", gas_limit=None, broadcast_mode=None)`

Submits `predictionmarket.settlement.v1.MsgMatchOrders`.

This is the most important relayer method.

Fields:

- `taker_order`: `Order` or dict
- `maker_orders`: list of `Order` or dict
- `taker_fill_amount`
- `maker_fill_amounts`
- `submitter`: optional explicit relayer address
- `surplus_recipient`: optional address for surplus handling
- `gas_limit`, `broadcast_mode`

Important notes:

- all orders must already be signed
- the SDK does not sign or verify order signatures for you
- the chain still verifies those signatures during execution
- the outer tx signer is the relayer `submitter`

Recommended relayer hot-path call:

```python
submission = client.match_orders(
    taker_order=taker_order,
    maker_orders=maker_orders,
    taker_fill_amount=taker_fill_amount,
    maker_fill_amounts=maker_fill_amounts,
    broadcast_mode="BROADCAST_MODE_SYNC",
)
```

### `cancel_orders(order_hashes, signer=None, principal="", gas_limit=None, broadcast_mode=None)`

Submits `MsgCancelOrders`.

Use this for relayer-driven cancels or delegated cancel flows where the native
tx signer is the configured relayer signer.

### `invalidate_nonce(min_valid_nonce, signer=None, principal="", gas_limit=None, broadcast_mode=None)`

Submits `MsgInvalidateNonce`.

### `approve_agent(agent, principal=None, expires_at_unix=0, gas_limit=None, broadcast_mode=None)`

Submits `MsgApproveAgent`.

### `revoke_agent(agent, principal=None, gas_limit=None, broadcast_mode=None)`

Submits `MsgRevokeAgent`.

### `pause_settlement(paused, authority=None, gas_limit=None, broadcast_mode=None)`

Submits `MsgPauseSettlement`.

### `set_matcher_authorization(matcher, allowed, authority=None, gas_limit=None, broadcast_mode=None)`

Submits `MsgSetMatcherAuthorization`.

## PoA

### `set_validator_set(validators, authority=None, gas_limit=None, broadcast_mode=None)`

Submits `MsgSetValidatorSet`.

Fields:

- `validators`: list of `ValidatorSlot`

### `update_poa_admin(new_admin, authority=None, gas_limit=None, broadcast_mode=None)`

Submits `MsgUpdateAdmin` for the PoA module.

## Operational Notes

### Sequence / Nonce Safety

This SDK already helps with the normal Cosmos relayer nonce problem:

- cached signer sequence
- serialized submit path per client instance
- sequence refresh on mismatch
- cache reset on ambiguous transport failure

But the recommended production model is still:

- one relayer key per queue
- one client instance per relayer worker
- multiple relayer keys if you want parallel throughput

### Efficiency

The client keeps a few useful things cached:

- `chain_id`
- relayer compressed pubkey
- protobuf `Any` wrapper for the relayer pubkey
- local next sequence

That keeps the hot submission path lighter than re-resolving everything on
every tx.

### Best Default for Hot Relayers

If the caller wants throughput plus honest status, the usual default is:

- call `sync_signer_state()` once
- submit with `BROADCAST_MODE_SYNC`
- separately poll/resolve txs only where needed

That is usually the best balance between latency and correctness for a live
relayer.
