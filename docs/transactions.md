# Transaction Methods

This file documents the high-level transaction methods exposed by
`PredchainSDKv2Client`.

All methods:

- submit directly to the chain
- return `TxSubmission`
- use the configured relayer key to sign the native Cosmos tx
- do not sign settlement orders

## Low-Level Methods

### `status() -> dict`

Fetches CometBFT status from the configured RPC endpoint.

### `chain_id(refresh: bool = False) -> str`

Returns the cached chain id or resolves it from RPC `/status`.

### `get_account_info(address: str | None = None, refresh_sequence_cache: bool = False) -> AccountInfo`

Fetches `account_number` and `sequence` for one chain account.

### `get_tx(tx_hash: str) -> dict`

Fetches one tx from chain REST by hash.

### `wait_for_tx(tx_hash: str, timeout_seconds: float | None = None) -> dict`

Polls RPC `/tx` until the tx is found or times out.

### `submit_message(message, signer_address=None, gas_limit=None, broadcast_mode=None, commit_timeout_seconds=None) -> TxSubmission`

Low-level submit path for already-built protobuf messages.

### `broadcast_tx_bytes(tx_bytes: bytes, mode=None) -> dict`

Broadcasts prebuilt tx bytes directly.

## Bank

### `send(to_address, amount, denom="uusdc", from_address=None, gas_limit=None, broadcast_mode=None)`

Builds and submits `cosmos.bank.v1beta1.MsgSend`.

## Testnet Mint

### `admin_mint_usdc(to, amount, authority=None, gas_limit=None, broadcast_mode=None)`

Builds and submits `predictionmarket.testnetmint.v1.MsgAdminMintUSDC`.

### `admin_burn_usdc(from_address, amount, authority=None, gas_limit=None, broadcast_mode=None)`

Builds and submits `predictionmarket.testnetmint.v1.MsgAdminBurnUSDC`.

### `update_testnetmint_admin(new_admin, authority=None, gas_limit=None, broadcast_mode=None)`

Builds and submits `predictionmarket.testnetmint.v1.MsgUpdateAdmin`.

## Markets

### `create_market(question, taker_fee_bps=100, metadata_uri="", authority=None, gas_limit=None, broadcast_mode=None)`

Creates one binary market.

### `create_parlay_market(question, legs, taker_fee_bps=100, metadata_uri="", authority=None, gas_limit=None, broadcast_mode=None)`

Creates one parlay market from underlying legs.

### `create_neg_risk_group(title, market_ids, metadata_uri="", authority=None, gas_limit=None, broadcast_mode=None)`

Creates one neg-risk group.

### `update_market_admin(new_admin, authority=None, gas_limit=None, broadcast_mode=None)`

Rotates the market admin.

### `convert_neg_risk_position(group_id, anchor_market_id, amount, direction, holder=None, gas_limit=None, broadcast_mode=None)`

Converts within one neg-risk group.

### `collapse_parlay_position(parlay_market_id, amount, holder=None, gas_limit=None, broadcast_mode=None)`

Collapses one parlay position.

### `pause_market(market_id, paused, authority=None, gas_limit=None, broadcast_mode=None)`

Pauses or unpauses one market.

### `set_market_fee(market_id, taker_fee_bps, authority=None, gas_limit=None, broadcast_mode=None)`

Updates one market fee.

### `resolve_market(market_id, winning_outcome, resolution_metadata_uri="", authority=None, gas_limit=None, broadcast_mode=None)`

Resolves one market.

## CTF

### `split_position(condition_id, amount, partition, collateral_denom="uusdc", parent_collection_id="0", holder=None, gas_limit=None, broadcast_mode=None)`

Splits collateral into conditional positions.

### `merge_positions(condition_id, amount, partition, collateral_denom="uusdc", parent_collection_id="0", holder=None, gas_limit=None, broadcast_mode=None)`

Merges sibling positions back into collateral.

### `redeem_positions(condition_id, index_sets, collateral_denom="uusdc", parent_collection_id="0", holder=None, gas_limit=None, broadcast_mode=None)`

Redeems winning positions.

## Settlement

### `match_orders(taker_order, maker_orders, taker_fill_amount, maker_fill_amounts, submitter=None, surplus_recipient="", gas_limit=None, broadcast_mode=None)`

Submits `MsgMatchOrders`.

Notes:

- `taker_order` and `maker_orders` must already contain valid order signatures.
- This method does not sign orders.
- This method only signs the outer relayer tx.

### `cancel_orders(order_hashes, signer=None, principal="", gas_limit=None, broadcast_mode=None)`

Cancels one or more orders by hash.

### `invalidate_nonce(min_valid_nonce, signer=None, principal="", gas_limit=None, broadcast_mode=None)`

Raises the minimum valid settlement nonce.

### `approve_agent(agent, principal=None, expires_at_unix=0, gas_limit=None, broadcast_mode=None)`

Approves an agent for one principal.

### `revoke_agent(agent, principal=None, gas_limit=None, broadcast_mode=None)`

Revokes an agent.

### `pause_settlement(paused, authority=None, gas_limit=None, broadcast_mode=None)`

Pauses or unpauses settlement.

### `set_matcher_authorization(matcher, allowed, authority=None, gas_limit=None, broadcast_mode=None)`

Allows or disallows one matcher.

## PoA

### `set_validator_set(validators, authority=None, gas_limit=None, broadcast_mode=None)`

Replaces the validator slot set.

### `update_poa_admin(new_admin, authority=None, gas_limit=None, broadcast_mode=None)`

Rotates the PoA admin.
