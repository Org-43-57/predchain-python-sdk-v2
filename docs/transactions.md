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

The same relayer client also exposes the normal read methods a relayer needs.
The idea is that the integrating service should not need a second SDK just to
inspect chain state before or after submission.

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

### `account(address) -> dict`

Fetches one normalized account detail document from the explorer read API.

Use this when you want:

- account number / sequence
- collateral balance summary
- granted agents
- principals that delegated to this account

### `accounts_index(sort_by="balance_desc", page=1, limit=25) -> dict`

Fetches paginated account summaries.

Useful when the relayer/service wants a simple sortable account index without
walking the full auth/bank state itself.

### `authorities() -> dict`

Fetches the current authority/admin surface:

- market admin
- settlement admin and matcher allowlist
- PoA admin
- testnet mint admin

This is the main read method for “who controls what right now”.

### `settlement_params() -> dict`

Fetches the settlement module params directly from the chain-native explorer API.

### `market(market_id) -> dict`

Fetches one normalized market detail response, including:

- core market metadata
- YES / NO position metadata
- neg-risk group detail when attached
- parlay composition when the market is a parlay
- reverse “used by parlays” references when applicable

### `markets(...) -> dict`

Fetches paginated market registry data with filters.

Supported filter kwargs:

- `market_type`
- `status`
- `contains`
- `group_id`
- `leg_market_id`
- `sort`
- `limit`
- `offset`

### `market_by_position(position_id) -> dict`

Resolves one position id back to its owning market detail.

### `neg_risk_group(group_id) -> dict`

Fetches one neg-risk group plus grouped market summaries.

### `agent_authorization(principal, agent) -> dict`

Fetches one exact settlement agent authorization edge.

### `agents_by_principal(principal, offset=0, limit=50) -> dict`

Lists paginated agents granted by one principal.

### `principals_by_agent(agent, offset=0, limit=50) -> dict`

Lists paginated principals that granted one agent.

### `order_status(order) -> dict`

Fetches current settlement state for one order:

- order hash
- filled maker amount
- remaining maker amount
- cancelled / nonce invalidated / expired flags
- fully-filled / active flags
- min valid nonce

### `order_fill(order) -> dict`

Focused version of `order_status()` for fill accounting only.

### `nonce_status(signer, nonce, principal=None) -> dict`

Checks whether one nonce is still valid for a signer/principal pair.

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

The same client also includes the broader chain tx helpers.

#### Market lifecycle and admin

- `create_market(...)`
- `create_parlay_market(...)`
- `create_neg_risk_group(...)`
- `update_neg_risk_group(...)`
- `pause_market(...)`
- `set_market_fee(...)`
- `resolve_market(...)`
- `update_market_admin(...)`

#### CTF and composable positions

- `split_position(...)`
- `merge_positions(...)`
- `redeem_positions(...)`
- `convert_neg_risk_position(...)`
- `collapse_parlay_position(...)`

#### Settlement and settlement admin

- `cancel_orders(...)`
- `invalidate_nonce(...)`
- `approve_agent(...)`
- `revoke_agent(...)`
- `pause_settlement(...)`
- `set_matcher_authorization(...)`

#### Chain admin

- `set_validator_set(...)`
- `update_poa_admin(...)`
- `admin_mint_usdc(...)`
- `admin_burn_usdc(...)`
- `update_testnetmint_admin(...)`

So v2 is not limited to “submit one match tx”.
It covers the non-trivial chain-native operational flows as well.

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
- [examples/query_and_market_admin.py](/Users/valkvalue/IdeaProjects/testss/predchain-python-sdk-v2/examples/query_and_market_admin.py)
