from __future__ import annotations

import hashlib
import json
import threading
import time
from typing import Any
from urllib import error, parse, request

from google.protobuf.any_pb2 import Any as AnyMessage

from cosmos.tx.signing.v1beta1 import signing_pb2
from cosmos.tx.v1beta1 import tx_pb2 as cosmos_tx_pb2
from predictionmarket.crypto.v1 import keys_pb2 as chain_keys_pb2

from .crypto import compressed_pubkey_from_private_key_hex, encode_base64
from .exceptions import CommitTimeoutError, PredchainHTTPError
from .messages import (
    build_msg_admin_burn_usdc,
    build_msg_admin_mint_usdc,
    build_msg_approve_agent,
    build_msg_cancel_orders,
    build_msg_collapse_parlay_position,
    build_msg_convert_neg_risk_position,
    build_msg_create_market,
    build_msg_create_neg_risk_group,
    build_msg_create_parlay_market,
    build_msg_invalidate_nonce,
    build_msg_match_orders,
    build_msg_merge_positions,
    build_msg_pause_market,
    build_msg_pause_settlement,
    build_msg_redeem_positions,
    build_msg_resolve_market,
    build_msg_revoke_agent,
    build_msg_send,
    build_msg_set_market_fee,
    build_msg_set_matcher_authorization,
    build_msg_set_validator_set,
    build_msg_split_position,
    build_msg_update_market_admin,
    build_msg_update_poa_admin,
    build_msg_update_testnetmint_admin,
    normalize_address,
)
from .models import AccountInfo, BroadcastMode, Coin, Order, ParlayLeg, RelayerConfig, TxSubmission, ValidatorSlot


class PredchainSDKv2Client:
    """
    Direct-chain Python relayer SDK for Predchain.

    This client does not sign orders. It expects order payloads to already
    contain valid signatures and only signs the native Cosmos transaction
    submitted by the relayer account.
    """

    DEFAULT_GAS_LIMITS: dict[str, int] = {
        "cosmos.bank.v1beta1.MsgSend": 120_000,
        "predictionmarket.testnetmint.v1.MsgAdminMintUSDC": 180_000,
        "predictionmarket.testnetmint.v1.MsgAdminBurnUSDC": 180_000,
        "predictionmarket.testnetmint.v1.MsgUpdateAdmin": 160_000,
        "predictionmarket.market.v1.MsgCreateMarket": 250_000,
        "predictionmarket.market.v1.MsgCreateParlayMarket": 400_000,
        "predictionmarket.market.v1.MsgCreateNegRiskGroup": 300_000,
        "predictionmarket.market.v1.MsgUpdateAdmin": 160_000,
        "predictionmarket.market.v1.MsgConvertNegRiskPosition": 300_000,
        "predictionmarket.market.v1.MsgCollapseParlayPosition": 260_000,
        "predictionmarket.market.v1.MsgPauseMarket": 150_000,
        "predictionmarket.market.v1.MsgSetMarketFee": 150_000,
        "predictionmarket.market.v1.MsgResolveMarket": 220_000,
        "predictionmarket.ctf.v1.MsgSplitPosition": 260_000,
        "predictionmarket.ctf.v1.MsgMergePositions": 260_000,
        "predictionmarket.ctf.v1.MsgRedeemPositions": 240_000,
        "predictionmarket.settlement.v1.MsgMatchOrders": 300_000,
        "predictionmarket.settlement.v1.MsgCancelOrders": 180_000,
        "predictionmarket.settlement.v1.MsgInvalidateNonce": 150_000,
        "predictionmarket.settlement.v1.MsgApproveAgent": 150_000,
        "predictionmarket.settlement.v1.MsgRevokeAgent": 150_000,
        "predictionmarket.settlement.v1.MsgPauseSettlement": 150_000,
        "predictionmarket.settlement.v1.MsgSetMatcherAuthorization": 150_000,
        "predictionmarket.poa.v1.MsgSetValidatorSet": 250_000,
        "predictionmarket.poa.v1.MsgUpdateAdmin": 160_000,
    }

    def __init__(
        self,
        api_url: str,
        rpc_url: str,
        signer_address: str,
        private_key_hex: str,
        chain_id: str | None = None,
        timeout_seconds: float = 30.0,
        default_broadcast_mode: BroadcastMode = "BROADCAST_MODE_BLOCK",
        default_commit_timeout_seconds: float = 25.0,
        max_sequence_retries: int = 2,
    ) -> None:
        self.cfg = RelayerConfig(
            api_url=api_url.rstrip("/"),
            rpc_url=rpc_url.rstrip("/"),
            signer_address=normalize_address(signer_address),
            private_key_hex=private_key_hex,
            chain_id=chain_id,
            timeout_seconds=timeout_seconds,
            default_broadcast_mode=default_broadcast_mode,
            default_commit_timeout_seconds=default_commit_timeout_seconds,
            max_sequence_retries=max_sequence_retries,
        )
        self._submit_lock = threading.Lock()
        self._account_number: int | None = None
        self._next_sequence: int | None = None

    def status(self) -> dict[str, Any]:
        """Fetch CometBFT status from the configured RPC endpoint."""
        return self._request_json("GET", self._rpc_url("/status"))

    def chain_id(self, refresh: bool = False) -> str:
        """Return the configured chain id, querying RPC status if needed."""
        if self.cfg.chain_id and not refresh:
            return self.cfg.chain_id
        payload = self.status()
        chain_id = str(payload.get("result", {}).get("node_info", {}).get("network", "")).strip()
        if not chain_id:
            raise RuntimeError("failed to resolve chain_id from rpc /status")
        self.cfg.chain_id = chain_id
        return chain_id

    def get_account_info(self, address: str | None = None, refresh_sequence_cache: bool = False) -> AccountInfo:
        """Fetch account_number and sequence for the signer or a target account."""
        normalized = normalize_address(address or self.cfg.signer_address)
        try:
            payload = self._request_json("GET", self._api_url(f"/cosmos/auth/v1beta1/accounts/{parse.quote(normalized, safe='')}"))
        except PredchainHTTPError as exc:
            if exc.status_code == 404:
                return AccountInfo(address=normalized, account_number=0, sequence=0, exists=False)
            raise
        account_number, sequence, ok = self._extract_sequence(payload.get("account"))
        if not ok:
            raise RuntimeError(f"failed to decode account_number/sequence for {normalized}")
        info = AccountInfo(address=normalized, account_number=account_number, sequence=sequence, exists=True)
        if refresh_sequence_cache and normalized == self.cfg.signer_address:
            self._account_number = info.account_number
            self._next_sequence = info.sequence
        return info

    def get_tx(self, tx_hash: str) -> dict[str, Any]:
        """Fetch a tx from the chain REST API by hash."""
        return self._request_json("GET", self._api_url(f"/cosmos/tx/v1beta1/txs/{parse.quote(tx_hash, safe='')}"))

    def wait_for_tx(self, tx_hash: str, timeout_seconds: float | None = None) -> dict[str, Any]:
        """Poll RPC /tx until the tx is committed or the timeout elapses."""
        timeout = timeout_seconds or self.cfg.default_commit_timeout_seconds
        deadline = time.time() + timeout
        normalized = tx_hash.strip().removeprefix("0x").upper()
        last_error: Exception | None = None
        while time.time() < deadline:
            try:
                payload = self._request_json(
                    "GET",
                    self._rpc_url(f"/tx?hash=0x{normalized}&prove=false"),
                )
                result = payload.get("result")
                if isinstance(result, dict) and result:
                    return result
            except Exception as exc:  # noqa: BLE001 - keep last rpc error for timeout context
                last_error = exc
            time.sleep(0.35)
        raise CommitTimeoutError(f"tx {tx_hash} was not committed within {timeout}s") from last_error

    def submit_message(
        self,
        message: Any,
        signer_address: str | None = None,
        gas_limit: int | None = None,
        broadcast_mode: BroadcastMode | None = None,
        commit_timeout_seconds: float | None = None,
    ) -> TxSubmission:
        """Build, sign, broadcast, and optionally wait for one native chain tx."""
        signer = normalize_address(signer_address or self.cfg.signer_address)
        if signer != self.cfg.signer_address:
            raise ValueError(
                f"message signer {signer} does not match configured relayer signer {self.cfg.signer_address}"
            )

        requested_mode, used_mode, wait_for_commit = self._normalize_broadcast_mode(broadcast_mode)
        gas = gas_limit or self._default_gas_limit(message)

        with self._submit_lock:
            account_info = self._ensure_sequence_state()
            attempt = 0
            while True:
                sequence = self._next_sequence if self._next_sequence is not None else account_info.sequence
                tx_bytes = self._build_signed_tx_bytes(
                    message=message,
                    account_number=account_info.account_number,
                    sequence=sequence,
                    gas_limit=gas,
                )
                local_hash = hashlib.sha256(tx_bytes).hexdigest().upper()
                broadcast = self._broadcast_tx_bytes(tx_bytes, used_mode)
                tx_response = broadcast.get("tx_response", {}) if isinstance(broadcast, dict) else {}
                broadcast_code = self._int_value(tx_response.get("code"))
                raw_log = str(tx_response.get("raw_log", "") or "")

                if broadcast_code != 0 and self._is_sequence_mismatch(raw_log):
                    if attempt >= self.cfg.max_sequence_retries:
                        return self._build_submission(
                            tx_hash=str(tx_response.get("txhash") or local_hash),
                            requested_mode=requested_mode,
                            used_mode=used_mode,
                            accepted=False,
                            committed=False,
                            success=False,
                            status="broadcast_rejected",
                            broadcast=tx_response,
                            committed_result=None,
                        )
                    attempt += 1
                    account_info = self.get_account_info(refresh_sequence_cache=True)
                    if not account_info.exists:
                        raise RuntimeError(f"signer account {self.cfg.signer_address} does not exist on-chain")
                    continue

                tx_hash = str(tx_response.get("txhash") or local_hash)
                accepted = broadcast_code == 0
                if accepted:
                    self._next_sequence = sequence + 1

                if not wait_for_commit or not accepted:
                    success = accepted
                    status = "accepted" if accepted else "broadcast_rejected"
                    return self._build_submission(
                        tx_hash=tx_hash,
                        requested_mode=requested_mode,
                        used_mode=used_mode,
                        accepted=accepted,
                        committed=False,
                        success=success,
                        status=status,
                        broadcast=tx_response,
                        committed_result=None,
                    )

                try:
                    committed = self.wait_for_tx(tx_hash, timeout_seconds=commit_timeout_seconds)
                except CommitTimeoutError:
                    return self._build_submission(
                        tx_hash=tx_hash,
                        requested_mode=requested_mode,
                        used_mode=used_mode,
                        accepted=True,
                        committed=False,
                        success=False,
                        status="commit_timeout",
                        broadcast=tx_response,
                        committed_result=None,
                    )

                committed_code = self._int_value(committed.get("tx_result", {}).get("code"))
                committed_success = committed_code == 0
                return self._build_submission(
                    tx_hash=tx_hash,
                    requested_mode=requested_mode,
                    used_mode=used_mode,
                    accepted=True,
                    committed=True,
                    success=committed_success,
                    status="committed_success" if committed_success else "committed_failure",
                    broadcast=tx_response,
                    committed_result=committed,
                )

    def broadcast_tx_bytes(self, tx_bytes: bytes, mode: BroadcastMode | None = None) -> dict[str, Any]:
        """Broadcast prebuilt tx bytes directly to the chain REST endpoint."""
        _, used_mode, _ = self._normalize_broadcast_mode(mode)
        return self._broadcast_tx_bytes(tx_bytes, used_mode)

    def send(
        self,
        to_address: str,
        amount: str | list[Coin],
        denom: str = "uusdc",
        from_address: str | None = None,
        gas_limit: int | None = None,
        broadcast_mode: BroadcastMode | None = None,
    ) -> TxSubmission:
        """Submit `cosmos.bank.v1beta1.MsgSend` from the configured relayer signer."""
        coins = amount if isinstance(amount, list) else [Coin(denom=denom, amount=str(amount))]
        msg = build_msg_send(from_address or self.cfg.signer_address, to_address, coins)
        return self.submit_message(msg, signer_address=msg.from_address, gas_limit=gas_limit, broadcast_mode=broadcast_mode)

    def admin_mint_usdc(self, to: str, amount: str, authority: str | None = None, gas_limit: int | None = None, broadcast_mode: BroadcastMode | None = None) -> TxSubmission:
        """Submit `MsgAdminMintUSDC` directly to chain REST."""
        msg = build_msg_admin_mint_usdc(authority or self.cfg.signer_address, to, amount)
        return self.submit_message(msg, signer_address=msg.authority, gas_limit=gas_limit, broadcast_mode=broadcast_mode)

    def admin_burn_usdc(self, from_address: str, amount: str, authority: str | None = None, gas_limit: int | None = None, broadcast_mode: BroadcastMode | None = None) -> TxSubmission:
        """Submit `MsgAdminBurnUSDC` directly to chain REST."""
        msg = build_msg_admin_burn_usdc(authority or self.cfg.signer_address, from_address, amount)
        return self.submit_message(msg, signer_address=msg.authority, gas_limit=gas_limit, broadcast_mode=broadcast_mode)

    def update_testnetmint_admin(self, new_admin: str, authority: str | None = None, gas_limit: int | None = None, broadcast_mode: BroadcastMode | None = None) -> TxSubmission:
        """Rotate the testnet mint module admin on-chain."""
        msg = build_msg_update_testnetmint_admin(authority or self.cfg.signer_address, new_admin)
        return self.submit_message(msg, signer_address=msg.authority, gas_limit=gas_limit, broadcast_mode=broadcast_mode)

    def create_market(self, question: str, taker_fee_bps: int = 100, metadata_uri: str = "", authority: str | None = None, gas_limit: int | None = None, broadcast_mode: BroadcastMode | None = None) -> TxSubmission:
        """Create a binary market directly on-chain."""
        msg = build_msg_create_market(authority or self.cfg.signer_address, question, metadata_uri, taker_fee_bps)
        return self.submit_message(msg, signer_address=msg.authority, gas_limit=gas_limit, broadcast_mode=broadcast_mode)

    def create_parlay_market(self, question: str, legs: list[ParlayLeg], taker_fee_bps: int = 100, metadata_uri: str = "", authority: str | None = None, gas_limit: int | None = None, broadcast_mode: BroadcastMode | None = None) -> TxSubmission:
        """Create a parlay market from underlying market legs."""
        msg = build_msg_create_parlay_market(authority or self.cfg.signer_address, question, metadata_uri, taker_fee_bps, legs)
        return self.submit_message(msg, signer_address=msg.authority, gas_limit=gas_limit, broadcast_mode=broadcast_mode)

    def create_neg_risk_group(self, title: str, market_ids: list[int], metadata_uri: str = "", authority: str | None = None, gas_limit: int | None = None, broadcast_mode: BroadcastMode | None = None) -> TxSubmission:
        """Create a neg-risk group on-chain."""
        msg = build_msg_create_neg_risk_group(authority or self.cfg.signer_address, title, metadata_uri, market_ids)
        return self.submit_message(msg, signer_address=msg.authority, gas_limit=gas_limit, broadcast_mode=broadcast_mode)

    def update_market_admin(self, new_admin: str, authority: str | None = None, gas_limit: int | None = None, broadcast_mode: BroadcastMode | None = None) -> TxSubmission:
        """Rotate the market module admin on-chain."""
        msg = build_msg_update_market_admin(authority or self.cfg.signer_address, new_admin)
        return self.submit_message(msg, signer_address=msg.authority, gas_limit=gas_limit, broadcast_mode=broadcast_mode)

    def convert_neg_risk_position(self, group_id: int, anchor_market_id: int, amount: str, direction: str, holder: str | None = None, gas_limit: int | None = None, broadcast_mode: BroadcastMode | None = None) -> TxSubmission:
        """Convert NO to ALL_YES or ALL_YES to NO within a neg-risk group."""
        msg = build_msg_convert_neg_risk_position(holder or self.cfg.signer_address, group_id, anchor_market_id, amount, direction)
        return self.submit_message(msg, signer_address=msg.holder, gas_limit=gas_limit, broadcast_mode=broadcast_mode)

    def collapse_parlay_position(self, parlay_market_id: int, amount: str, holder: str | None = None, gas_limit: int | None = None, broadcast_mode: BroadcastMode | None = None) -> TxSubmission:
        """Collapse a parlay position back into its target underlying position."""
        msg = build_msg_collapse_parlay_position(holder or self.cfg.signer_address, parlay_market_id, amount)
        return self.submit_message(msg, signer_address=msg.holder, gas_limit=gas_limit, broadcast_mode=broadcast_mode)

    def pause_market(self, market_id: int, paused: bool, authority: str | None = None, gas_limit: int | None = None, broadcast_mode: BroadcastMode | None = None) -> TxSubmission:
        """Pause or unpause one market on-chain."""
        msg = build_msg_pause_market(authority or self.cfg.signer_address, market_id, paused)
        return self.submit_message(msg, signer_address=msg.authority, gas_limit=gas_limit, broadcast_mode=broadcast_mode)

    def set_market_fee(self, market_id: int, taker_fee_bps: int, authority: str | None = None, gas_limit: int | None = None, broadcast_mode: BroadcastMode | None = None) -> TxSubmission:
        """Update the taker fee of an existing market."""
        msg = build_msg_set_market_fee(authority or self.cfg.signer_address, market_id, taker_fee_bps)
        return self.submit_message(msg, signer_address=msg.authority, gas_limit=gas_limit, broadcast_mode=broadcast_mode)

    def resolve_market(self, market_id: int, winning_outcome: str, resolution_metadata_uri: str = "", authority: str | None = None, gas_limit: int | None = None, broadcast_mode: BroadcastMode | None = None) -> TxSubmission:
        """Resolve a market to its winning outcome."""
        msg = build_msg_resolve_market(authority or self.cfg.signer_address, market_id, winning_outcome, resolution_metadata_uri)
        return self.submit_message(msg, signer_address=msg.authority, gas_limit=gas_limit, broadcast_mode=broadcast_mode)

    def split_position(self, condition_id: str, amount: str, partition: list[int], collateral_denom: str = "uusdc", parent_collection_id: str = "0", holder: str | None = None, gas_limit: int | None = None, broadcast_mode: BroadcastMode | None = None) -> TxSubmission:
        """Split collateral into CTF positions."""
        msg = build_msg_split_position(holder or self.cfg.signer_address, collateral_denom, parent_collection_id, condition_id, partition, amount)
        return self.submit_message(msg, signer_address=msg.holder, gas_limit=gas_limit, broadcast_mode=broadcast_mode)

    def merge_positions(self, condition_id: str, amount: str, partition: list[int], collateral_denom: str = "uusdc", parent_collection_id: str = "0", holder: str | None = None, gas_limit: int | None = None, broadcast_mode: BroadcastMode | None = None) -> TxSubmission:
        """Merge sibling CTF positions back into collateral."""
        msg = build_msg_merge_positions(holder or self.cfg.signer_address, collateral_denom, parent_collection_id, condition_id, partition, amount)
        return self.submit_message(msg, signer_address=msg.holder, gas_limit=gas_limit, broadcast_mode=broadcast_mode)

    def redeem_positions(self, condition_id: str, index_sets: list[int], collateral_denom: str = "uusdc", parent_collection_id: str = "0", holder: str | None = None, gas_limit: int | None = None, broadcast_mode: BroadcastMode | None = None) -> TxSubmission:
        """Redeem winning CTF positions for collateral."""
        msg = build_msg_redeem_positions(holder or self.cfg.signer_address, collateral_denom, parent_collection_id, condition_id, index_sets)
        return self.submit_message(msg, signer_address=msg.holder, gas_limit=gas_limit, broadcast_mode=broadcast_mode)

    def match_orders(self, taker_order: Order | dict[str, Any], maker_orders: list[Order | dict[str, Any]], taker_fill_amount: str, maker_fill_amounts: list[str], submitter: str | None = None, surplus_recipient: str = "", gas_limit: int | None = None, broadcast_mode: BroadcastMode | None = None) -> TxSubmission:
        """Submit one `MsgMatchOrders` using already-signed off-chain orders."""
        msg = build_msg_match_orders(submitter or self.cfg.signer_address, taker_order, maker_orders, taker_fill_amount, maker_fill_amounts, surplus_recipient)
        return self.submit_message(msg, signer_address=msg.submitter, gas_limit=gas_limit, broadcast_mode=broadcast_mode)

    def cancel_orders(self, order_hashes: list[str], signer: str | None = None, principal: str = "", gas_limit: int | None = None, broadcast_mode: BroadcastMode | None = None) -> TxSubmission:
        """Cancel one or more settlement orders by hash."""
        msg = build_msg_cancel_orders(signer or self.cfg.signer_address, order_hashes, principal)
        return self.submit_message(msg, signer_address=msg.signer, gas_limit=gas_limit, broadcast_mode=broadcast_mode)

    def invalidate_nonce(self, min_valid_nonce: int, signer: str | None = None, principal: str = "", gas_limit: int | None = None, broadcast_mode: BroadcastMode | None = None) -> TxSubmission:
        """Raise the minimum valid nonce for one signer/principal pair."""
        msg = build_msg_invalidate_nonce(signer or self.cfg.signer_address, min_valid_nonce, principal)
        return self.submit_message(msg, signer_address=msg.signer, gas_limit=gas_limit, broadcast_mode=broadcast_mode)

    def approve_agent(self, agent: str, principal: str | None = None, expires_at_unix: int = 0, gas_limit: int | None = None, broadcast_mode: BroadcastMode | None = None) -> TxSubmission:
        """Approve an agent for a principal account."""
        msg = build_msg_approve_agent(principal or self.cfg.signer_address, agent, expires_at_unix)
        return self.submit_message(msg, signer_address=msg.principal, gas_limit=gas_limit, broadcast_mode=broadcast_mode)

    def revoke_agent(self, agent: str, principal: str | None = None, gas_limit: int | None = None, broadcast_mode: BroadcastMode | None = None) -> TxSubmission:
        """Revoke an agent authorization."""
        msg = build_msg_revoke_agent(principal or self.cfg.signer_address, agent)
        return self.submit_message(msg, signer_address=msg.principal, gas_limit=gas_limit, broadcast_mode=broadcast_mode)

    def pause_settlement(self, paused: bool, authority: str | None = None, gas_limit: int | None = None, broadcast_mode: BroadcastMode | None = None) -> TxSubmission:
        """Pause or unpause the settlement module."""
        msg = build_msg_pause_settlement(authority or self.cfg.signer_address, paused)
        return self.submit_message(msg, signer_address=msg.authority, gas_limit=gas_limit, broadcast_mode=broadcast_mode)

    def set_matcher_authorization(self, matcher: str, allowed: bool, authority: str | None = None, gas_limit: int | None = None, broadcast_mode: BroadcastMode | None = None) -> TxSubmission:
        """Allow or disallow one matcher address."""
        msg = build_msg_set_matcher_authorization(authority or self.cfg.signer_address, matcher, allowed)
        return self.submit_message(msg, signer_address=msg.authority, gas_limit=gas_limit, broadcast_mode=broadcast_mode)

    def set_validator_set(self, validators: list[ValidatorSlot], authority: str | None = None, gas_limit: int | None = None, broadcast_mode: BroadcastMode | None = None) -> TxSubmission:
        """Replace the PoA validator slot set."""
        msg = build_msg_set_validator_set(authority or self.cfg.signer_address, validators)
        return self.submit_message(msg, signer_address=msg.authority, gas_limit=gas_limit, broadcast_mode=broadcast_mode)

    def update_poa_admin(self, new_admin: str, authority: str | None = None, gas_limit: int | None = None, broadcast_mode: BroadcastMode | None = None) -> TxSubmission:
        """Rotate the PoA module admin."""
        msg = build_msg_update_poa_admin(authority or self.cfg.signer_address, new_admin)
        return self.submit_message(msg, signer_address=msg.authority, gas_limit=gas_limit, broadcast_mode=broadcast_mode)

    def _api_url(self, path: str) -> str:
        return f"{self.cfg.api_url}/{path.lstrip('/')}"

    def _rpc_url(self, path: str) -> str:
        return f"{self.cfg.rpc_url}/{path.lstrip('/')}"

    def _request_json(self, method: str, url: str, body: Any | None = None) -> dict[str, Any]:
        payload = None
        headers = {"Accept": "application/json"}
        if body is not None:
            payload = json.dumps(body).encode("utf-8")
            headers["Content-Type"] = "application/json"
        req = request.Request(url, data=payload, headers=headers, method=method.upper())
        try:
            with request.urlopen(req, timeout=self.cfg.timeout_seconds) as response:
                raw = response.read()
        except error.HTTPError as exc:
            raw = exc.read().decode("utf-8", errors="replace")
            try:
                decoded = json.loads(raw)
            except json.JSONDecodeError:
                decoded = raw
            message = decoded.get("message") if isinstance(decoded, dict) else str(decoded)
            if isinstance(decoded, dict) and decoded.get("error"):
                message = decoded.get("error")
            raise PredchainHTTPError(exc.code, str(message or raw), decoded) from exc
        except error.URLError as exc:
            raise PredchainHTTPError(0, f"request failed: {exc.reason}") from exc

        if not raw:
            return {}
        decoded = json.loads(raw.decode("utf-8"))
        if isinstance(decoded, dict) and decoded.get("error"):
            raise PredchainHTTPError(502, str(decoded["error"]), decoded)
        return decoded

    def _ensure_sequence_state(self) -> AccountInfo:
        if self._account_number is not None and self._next_sequence is not None:
            return AccountInfo(
                address=self.cfg.signer_address,
                account_number=self._account_number,
                sequence=self._next_sequence,
                exists=True,
            )
        info = self.get_account_info(refresh_sequence_cache=True)
        if not info.exists:
            raise RuntimeError(f"signer account {self.cfg.signer_address} does not exist on-chain")
        return info

    def _default_gas_limit(self, message: Any) -> int:
        return self.DEFAULT_GAS_LIMITS.get(message.DESCRIPTOR.full_name, 500_000)

    def _pack_any(self, message: Any) -> AnyMessage:
        return AnyMessage(
            type_url=f"/{message.DESCRIPTOR.full_name}",
            value=message.SerializeToString(),
        )

    def _build_signed_tx_bytes(self, message: Any, account_number: int, sequence: int, gas_limit: int) -> bytes:
        body = cosmos_tx_pb2.TxBody(messages=[self._pack_any(message)])
        body_bytes = body.SerializeToString()

        pub_key = chain_keys_pb2.PubKey(key=compressed_pubkey_from_private_key_hex(self.cfg.private_key_hex))
        signer_info = cosmos_tx_pb2.SignerInfo(
            public_key=self._pack_any(pub_key),
            mode_info=cosmos_tx_pb2.ModeInfo(
                single=cosmos_tx_pb2.ModeInfo.Single(mode=signing_pb2.SIGN_MODE_DIRECT)
            ),
            sequence=int(sequence),
        )
        auth_info = cosmos_tx_pb2.AuthInfo(
            signer_infos=[signer_info],
            fee=cosmos_tx_pb2.Fee(amount=[], gas_limit=int(gas_limit)),
        )
        auth_info_bytes = auth_info.SerializeToString()

        sign_doc = cosmos_tx_pb2.SignDoc(
            body_bytes=body_bytes,
            auth_info_bytes=auth_info_bytes,
            chain_id=self.chain_id(),
            account_number=int(account_number),
        )
        from .crypto import sign_direct  # imported lazily so package import stays light

        signature = sign_direct(self.cfg.private_key_hex, sign_doc.SerializeToString())
        tx_raw = cosmos_tx_pb2.TxRaw(
            body_bytes=body_bytes,
            auth_info_bytes=auth_info_bytes,
            signatures=[signature],
        )
        return tx_raw.SerializeToString()

    def _broadcast_tx_bytes(self, tx_bytes: bytes, mode: BroadcastMode) -> dict[str, Any]:
        return self._request_json(
            "POST",
            self._api_url("/cosmos/tx/v1beta1/txs"),
            {
                "tx_bytes": encode_base64(tx_bytes),
                "mode": mode,
            },
        )

    def _normalize_broadcast_mode(self, requested: BroadcastMode | None) -> tuple[BroadcastMode, BroadcastMode, bool]:
        raw = (requested or self.cfg.default_broadcast_mode or "BROADCAST_MODE_SYNC").strip().upper()
        aliases = {
            "SYNC": "BROADCAST_MODE_SYNC",
            "ASYNC": "BROADCAST_MODE_ASYNC",
            "BLOCK": "BROADCAST_MODE_BLOCK",
            "UNSPECIFIED": "BROADCAST_MODE_UNSPECIFIED",
        }
        raw = aliases.get(raw, raw)
        if raw in {"BROADCAST_MODE_UNSPECIFIED", "BROADCAST_MODE_SYNC"}:
            return raw, "BROADCAST_MODE_SYNC", False
        if raw == "BROADCAST_MODE_ASYNC":
            return raw, raw, False
        if raw == "BROADCAST_MODE_BLOCK":
            return raw, "BROADCAST_MODE_SYNC", True
        raise ValueError(
            f"unsupported broadcast mode {requested!r}; expected BROADCAST_MODE_ASYNC, BROADCAST_MODE_SYNC, or BROADCAST_MODE_BLOCK"
        )

    def _build_submission(
        self,
        tx_hash: str,
        requested_mode: BroadcastMode,
        used_mode: BroadcastMode,
        accepted: bool,
        committed: bool,
        success: bool,
        status: str,
        broadcast: dict[str, Any],
        committed_result: dict[str, Any] | None,
    ) -> TxSubmission:
        tx_result = committed_result.get("tx_result", {}) if committed_result else {}
        return TxSubmission(
            tx_hash=tx_hash,
            mode_requested=requested_mode,
            mode_used=used_mode,
            accepted=accepted,
            committed=committed,
            success=success,
            status=status,
            broadcast_code=self._int_value(broadcast.get("code")),
            broadcast_raw_log=str(broadcast.get("raw_log", "") or ""),
            broadcast_height=self._int_value(broadcast.get("height")),
            gas_wanted=self._int_value(broadcast.get("gas_wanted")),
            gas_used=self._int_value(broadcast.get("gas_used")),
            committed_code=self._int_value(tx_result.get("code")) if committed_result else None,
            committed_raw_log=str(tx_result.get("log", "") or "") if committed_result else None,
            committed_height=self._int_value(committed_result.get("height")) if committed_result else None,
            raw_broadcast=broadcast,
            raw_committed=committed_result,
        )

    def _extract_sequence(self, node: Any) -> tuple[int, int, bool]:
        if isinstance(node, dict):
            account_number, has_account_number = self._read_uint64(node, "account_number")
            sequence, has_sequence = self._read_uint64(node, "sequence")
            if has_account_number and has_sequence:
                return account_number, sequence, True
            for value in node.values():
                account_number, sequence, ok = self._extract_sequence(value)
                if ok:
                    return account_number, sequence, True
        if isinstance(node, list):
            for value in node:
                account_number, sequence, ok = self._extract_sequence(value)
                if ok:
                    return account_number, sequence, True
        return 0, 0, False

    def _read_uint64(self, node: dict[str, Any], key: str) -> tuple[int, bool]:
        if key not in node:
            return 0, False
        try:
            return self._int_value(node[key]), True
        except (TypeError, ValueError):
            return 0, False

    def _int_value(self, value: Any) -> int:
        if value is None:
            return 0
        if isinstance(value, bool):
            return int(value)
        if isinstance(value, (int, float)):
            return int(value)
        text = str(value).strip()
        if not text:
            return 0
        return int(text, 10)

    def _is_sequence_mismatch(self, raw_log: str) -> bool:
        lowered = raw_log.lower()
        return "incorrect account sequence" in lowered or "account sequence mismatch" in lowered


PredchainRelayerClient = PredchainSDKv2Client
