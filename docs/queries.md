# Predchain Python SDK v2 Query Reference

This SDK is not submit-only. The same client is expected to cover the main
read paths a relayer or operator needs when preparing and validating txs.

## Infrastructure and signer readiness

### `status()`

Returns raw CometBFT `/status`.

Use it when you want:

- latest known height
- node catching-up status
- validator identity fields

### `health()`

Returns a relayer-oriented summary:

- chain id
- latest height / latest block time
- node catching-up status
- signer existence
- signer account number / sequence

### `get_account_info(address=None, refresh_sequence_cache=False)`

Fetches auth account number and sequence for the configured relayer signer or
another address.

### `signer_status(refresh=True)`

Returns signer-focused status, including:

- on-chain sequence
- cached next sequence inside the SDK
- chain id

### `balances(address=None)`

Fetches all bank balances for one address.

## Explorer-backed read surface

These methods use the chain-native explorer read API, not the demo API.

### `account(address)`

Returns one normalized account detail response.

### `accounts_index(sort_by="balance_desc", page=1, limit=25)`

Returns paginated account summaries.

### `authorities()`

Returns the current authority surface:

- `market_admin`
- `poa_admin`
- `testnetmint_admin`
- nested `settlement` admin / treasury / paused / allowed_matchers

### `settlement_params()`

Returns the settlement params object directly.

### `market(market_id)`

Returns one normalized market detail response.

### `markets(...)`

Returns paginated market registry data.

Supported filters:

- `market_type`
- `status`
- `contains`
- `group_id`
- `leg_market_id`
- `sort`
- `limit`
- `offset`

### `market_by_position(position_id)`

Resolves one position id back to its owning market.

### `neg_risk_group(group_id)`

Returns one neg-risk group and its grouped markets.

## Settlement state inspection

### `agent_authorization(principal, agent)`

Fetches one exact agent authorization edge.

### `agents_by_principal(principal, offset=0, limit=50)`

Lists agents granted by one principal.

### `principals_by_agent(agent, offset=0, limit=50)`

Lists principals that granted one agent.

### `order_status(order)`

Returns full order state:

- `order_hash`
- `filled_maker_amount`
- `remaining_maker_amount`
- `cancelled`
- `nonce_invalidated`
- `expired`
- `fully_filled`
- `active`
- `min_valid_nonce`

### `order_fill(order)`

Returns only the fill-oriented subset:

- `order_hash`
- `filled_maker_amount`
- `remaining_maker_amount`
- `fully_filled`

### `nonce_status(signer, nonce, principal=None)`

Returns:

- `signer`
- `principal`
- `nonce`
- `min_valid_nonce`
- `is_valid`

## Tx status inspection

### `get_tx(tx_hash)`

Returns chain REST tx data by hash.

### `wait_for_tx(tx_hash, timeout_seconds=None)`

Polls RPC until the tx is seen committed or the timeout elapses.
