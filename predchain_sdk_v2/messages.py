from __future__ import annotations

from typing import Sequence

from cosmos.bank.v1beta1 import tx_pb2 as bank_tx_pb2
from cosmos.base.v1beta1 import coin_pb2 as cosmos_coin_pb2
from predictionmarket.ctf.v1 import tx_pb2 as ctf_tx_pb2
from predictionmarket.market.v1 import tx_pb2 as market_tx_pb2
from predictionmarket.poa.v1 import tx_pb2 as poa_tx_pb2
from predictionmarket.settlement.v1 import tx_pb2 as settlement_tx_pb2
from predictionmarket.testnetmint.v1 import tx_pb2 as testnetmint_tx_pb2

from .crypto import decode_hex, normalize_hex
from .models import Coin, MatchOrder, Order, ParlayLeg, ParlayOrder, ValidatorSlot

UINT256_MAX = (1 << 256) - 1


def normalize_address(value: str) -> str:
    return f"0x{normalize_hex(value).lower()}"


def normalize_uint256(value: int | str, field_name: str) -> str:
    try:
        normalized = int(str(value), 0)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{field_name} must be a valid uint256") from exc
    if normalized < 0:
        raise ValueError(f"{field_name} must be non-negative")
    if normalized > UINT256_MAX:
        raise ValueError(f"{field_name} must fit in uint256")
    return str(normalized)


def coins_to_proto(coins: Sequence[Coin]) -> list[cosmos_coin_pb2.Coin]:
    return [cosmos_coin_pb2.Coin(denom=coin.denom, amount=str(coin.amount)) for coin in coins]


def _signature_bytes(signature: bytes | str) -> bytes:
    if isinstance(signature, str):
        return decode_hex(signature) if signature.strip() else b""
    return bytes(signature)


def _settlement_parlay_legs(legs: Sequence[ParlayLeg | dict]) -> list[settlement_tx_pb2.ParlayOrderLeg]:
    out: list[settlement_tx_pb2.ParlayOrderLeg] = []
    for leg in legs:
        if isinstance(leg, dict):
            leg = ParlayLeg(**leg)
        out.append(settlement_tx_pb2.ParlayOrderLeg(market_id=int(leg.market_id), required_outcome=str(leg.required_outcome)))
    return out


def _token_order_ref(token_id: str) -> settlement_tx_pb2.OrderRef:
    return settlement_tx_pb2.OrderRef(token_id=str(token_id))


def _parlay_order_ref(legs: Sequence[ParlayLeg | dict], position_side: str) -> settlement_tx_pb2.OrderRef:
    return settlement_tx_pb2.OrderRef(
        parlay=settlement_tx_pb2.ParlayRef(
            legs=_settlement_parlay_legs(legs),
            position_side=str(position_side),
        )
    )


def order_to_proto(order: Order | dict) -> settlement_tx_pb2.Order:
    if isinstance(order, dict):
        order = Order(**order)
    return settlement_tx_pb2.Order(
        salt=normalize_uint256(order.salt, "salt"),
        maker=normalize_address(order.maker),
        signer=normalize_address(order.signer),
        taker=normalize_address(order.taker) if str(order.taker).strip() else "",
        ref=_token_order_ref(order.token_id),
        maker_amount=str(order.maker_amount),
        taker_amount=str(order.taker_amount),
        expiration=int(order.expiration),
        nonce=normalize_uint256(order.nonce, "nonce"),
        fee_rate_bps=int(order.fee_rate_bps),
        side=str(order.side),
        signature_type=str(order.signature_type),
        signature=_signature_bytes(order.signature),
    )


def match_order_to_proto(order: MatchOrder | dict) -> settlement_tx_pb2.Order:
    if isinstance(order, dict):
        token_id = str(order.get("token_id", "")).strip()
        legs = order.get("legs") or []
        position_side = str(order.get("position_side", "")).strip()
        if token_id and (legs or position_side):
            raise ValueError("match order must specify either token_id or legs+position_side, not both")
        if token_id:
            order = Order(**order)
        elif legs or position_side:
            order = ParlayOrder(**order)
        else:
            raise ValueError("match order must specify token_id or legs+position_side")
    if isinstance(order, ParlayOrder):
        return settlement_tx_pb2.Order(
            salt=normalize_uint256(order.salt, "salt"),
            maker=normalize_address(order.maker),
            signer=normalize_address(order.signer),
            taker=normalize_address(order.taker) if str(order.taker).strip() else "",
            ref=_parlay_order_ref(order.legs, order.position_side),
            maker_amount=str(order.maker_amount),
            taker_amount=str(order.taker_amount),
            expiration=int(order.expiration),
            nonce=normalize_uint256(order.nonce, "nonce"),
            fee_rate_bps=int(order.fee_rate_bps),
            side=str(order.side),
            signature_type=str(order.signature_type),
            signature=_signature_bytes(order.signature),
        )
    return order_to_proto(order)


def parlay_order_to_proto(order: ParlayOrder | dict) -> settlement_tx_pb2.ParlayOrder:
    if isinstance(order, dict):
        order = ParlayOrder(**order)
    return settlement_tx_pb2.ParlayOrder(
        salt=normalize_uint256(order.salt, "salt"),
        maker=normalize_address(order.maker),
        signer=normalize_address(order.signer),
        taker=normalize_address(order.taker) if str(order.taker).strip() else "",
        legs=_settlement_parlay_legs(order.legs),
        position_side=str(order.position_side),
        maker_amount=str(order.maker_amount),
        taker_amount=str(order.taker_amount),
        expiration=int(order.expiration),
        nonce=normalize_uint256(order.nonce, "nonce"),
        fee_rate_bps=int(order.fee_rate_bps),
        side=str(order.side),
        signature_type=str(order.signature_type),
        signature=_signature_bytes(order.signature),
    )


def parlay_legs_to_proto(legs: Sequence[ParlayLeg]) -> list[market_tx_pb2.ParlayLeg]:
    out: list[market_tx_pb2.ParlayLeg] = []
    for leg in legs:
        if isinstance(leg, dict):
            leg = ParlayLeg(**leg)
        out.append(market_tx_pb2.ParlayLeg(market_id=int(leg.market_id), required_outcome=str(leg.required_outcome)))
    return out


def validator_slots_to_proto(slots: Sequence[ValidatorSlot]) -> list[poa_tx_pb2.ValidatorSlot]:
    out: list[poa_tx_pb2.ValidatorSlot] = []
    for slot in slots:
        if isinstance(slot, dict):
            slot = ValidatorSlot(**slot)
        pub_key = slot.consensus_pub_key
        if isinstance(pub_key, str):
            pub_key_bytes = decode_hex(pub_key) if pub_key.strip() else b""
        else:
            pub_key_bytes = bytes(pub_key)
        out.append(
            poa_tx_pb2.ValidatorSlot(
                index=int(slot.index),
                name=str(slot.name),
                consensus_address=normalize_address(slot.consensus_address),
                consensus_pub_key=pub_key_bytes,
                power=int(slot.power),
            )
        )
    return out


def build_msg_send(from_address: str, to_address: str, amount: Sequence[Coin]) -> bank_tx_pb2.MsgSend:
    return bank_tx_pb2.MsgSend(
        from_address=normalize_address(from_address),
        to_address=normalize_address(to_address),
        amount=coins_to_proto(amount),
    )


def build_msg_admin_mint_usdc(authority: str, to: str, amount: str) -> testnetmint_tx_pb2.MsgAdminMintUSDC:
    return testnetmint_tx_pb2.MsgAdminMintUSDC(authority=normalize_address(authority), to=normalize_address(to), amount=str(amount))


def build_msg_admin_burn_usdc(authority: str, from_address: str, amount: str) -> testnetmint_tx_pb2.MsgAdminBurnUSDC:
    return testnetmint_tx_pb2.MsgAdminBurnUSDC(
        authority=normalize_address(authority),
        amount=str(amount),
        **{"from": normalize_address(from_address)},
    )


def build_msg_update_testnetmint_admin(authority: str, new_admin: str) -> testnetmint_tx_pb2.MsgUpdateAdmin:
    return testnetmint_tx_pb2.MsgUpdateAdmin(authority=normalize_address(authority), new_admin=normalize_address(new_admin))


def build_msg_create_market(authority: str, question: str, metadata_uri: str) -> market_tx_pb2.MsgCreateMarket:
    return market_tx_pb2.MsgCreateMarket(
        authority=normalize_address(authority),
        question=str(question),
        metadata_uri=str(metadata_uri),
    )


def build_msg_create_parlay_market(authority: str, legs: Sequence[ParlayLeg]) -> market_tx_pb2.MsgCreateParlayMarket:
    return market_tx_pb2.MsgCreateParlayMarket(
        authority=normalize_address(authority),
        legs=parlay_legs_to_proto(legs),
    )


def build_msg_create_neg_risk_group(authority: str, title: str, metadata_uri: str, market_ids: Sequence[int]) -> market_tx_pb2.MsgCreateNegRiskGroup:
    return market_tx_pb2.MsgCreateNegRiskGroup(
        authority=normalize_address(authority),
        title=str(title),
        metadata_uri=str(metadata_uri),
        market_ids=[int(market_id) for market_id in market_ids],
    )


def build_msg_update_neg_risk_group(authority: str, group_id: int, add_market_ids: Sequence[int], title: str = "", metadata_uri: str = "") -> market_tx_pb2.MsgUpdateNegRiskGroup:
    return market_tx_pb2.MsgUpdateNegRiskGroup(
        authority=normalize_address(authority),
        group_id=int(group_id),
        title=str(title),
        metadata_uri=str(metadata_uri),
        add_market_ids=[int(market_id) for market_id in add_market_ids],
    )


def build_msg_update_market_admin(authority: str, new_admin: str) -> market_tx_pb2.MsgUpdateAdmin:
    return market_tx_pb2.MsgUpdateAdmin(authority=normalize_address(authority), new_admin=normalize_address(new_admin))


def build_msg_convert_neg_risk_position(holder: str, group_id: int, anchor_market_id: int, amount: str, direction: str) -> market_tx_pb2.MsgConvertNegRiskPosition:
    return market_tx_pb2.MsgConvertNegRiskPosition(
        holder=normalize_address(holder),
        group_id=int(group_id),
        anchor_market_id=int(anchor_market_id),
        amount=str(amount),
        direction=str(direction),
    )


def build_msg_collapse_parlay_position(holder: str, parlay_market_id: int, amount: str) -> market_tx_pb2.MsgCollapseParlayPosition:
    return market_tx_pb2.MsgCollapseParlayPosition(
        holder=normalize_address(holder),
        parlay_market_id=int(parlay_market_id),
        amount=str(amount),
    )


def build_msg_pause_market(authority: str, market_id: int, paused: bool) -> market_tx_pb2.MsgPauseMarket:
    return market_tx_pb2.MsgPauseMarket(authority=normalize_address(authority), market_id=int(market_id), paused=bool(paused))


def build_msg_resolve_market(authority: str, market_id: int, winning_outcome: str, resolution_metadata_uri: str) -> market_tx_pb2.MsgResolveMarket:
    return market_tx_pb2.MsgResolveMarket(
        authority=normalize_address(authority),
        market_id=int(market_id),
        winning_outcome=str(winning_outcome),
        resolution_metadata_uri=str(resolution_metadata_uri),
    )


def build_msg_split_position(holder: str, collateral_denom: str, parent_collection_id: str, condition_id: str, partition: Sequence[int], amount: str, actor: str = "") -> ctf_tx_pb2.MsgSplitPosition:
    normalized_holder = normalize_address(holder)
    return ctf_tx_pb2.MsgSplitPosition(
        actor=normalize_address(actor) if str(actor).strip() else normalized_holder,
        holder=normalized_holder,
        collateral_denom=str(collateral_denom),
        parent_collection_id=str(parent_collection_id),
        condition_id=str(condition_id),
        partition=[int(index) for index in partition],
        amount=str(amount),
    )


def build_msg_merge_positions(holder: str, collateral_denom: str, parent_collection_id: str, condition_id: str, partition: Sequence[int], amount: str, actor: str = "") -> ctf_tx_pb2.MsgMergePositions:
    normalized_holder = normalize_address(holder)
    return ctf_tx_pb2.MsgMergePositions(
        actor=normalize_address(actor) if str(actor).strip() else normalized_holder,
        holder=normalized_holder,
        collateral_denom=str(collateral_denom),
        parent_collection_id=str(parent_collection_id),
        condition_id=str(condition_id),
        partition=[int(index) for index in partition],
        amount=str(amount),
    )


def build_msg_redeem_positions(holder: str, collateral_denom: str, parent_collection_id: str, condition_id: str, index_sets: Sequence[int], actor: str = "") -> ctf_tx_pb2.MsgRedeemPositions:
    return ctf_tx_pb2.MsgRedeemPositions(
        holder=normalize_address(holder),
        collateral_denom=str(collateral_denom),
        parent_collection_id=str(parent_collection_id),
        condition_id=str(condition_id),
        index_sets=[int(index) for index in index_sets],
        actor=normalize_address(actor) if str(actor).strip() else "",
    )


def build_msg_match_orders(submitter: str, taker_order: MatchOrder | dict, maker_orders: Sequence[MatchOrder | dict], taker_fill_amount: str, maker_fill_amounts: Sequence[str], surplus_recipient: str = "", match_fee_bps: int | None = None) -> settlement_tx_pb2.MsgMatchOrders:
    payload = settlement_tx_pb2.MsgMatchOrders(
        submitter=normalize_address(submitter),
        taker_order=match_order_to_proto(taker_order),
        maker_orders=[match_order_to_proto(order) for order in maker_orders],
        taker_fill_amount=str(taker_fill_amount),
        maker_fill_amounts=[str(value) for value in maker_fill_amounts],
        surplus_recipient=normalize_address(surplus_recipient) if str(surplus_recipient).strip() else "",
    )
    if match_fee_bps is not None:
        payload.match_fee_bps = int(match_fee_bps)
    return payload


def build_msg_ensure_parlay_and_match_orders(
    submitter: str,
    taker_order: ParlayOrder | dict,
    maker_orders: Sequence[ParlayOrder | dict],
    taker_fill_amount: str,
    maker_fill_amounts: Sequence[str],
    surplus_recipient: str = "",
    match_fee_bps: int | None = None,
) -> settlement_tx_pb2.MsgEnsureParlayAndMatchOrders:
    payload = settlement_tx_pb2.MsgEnsureParlayAndMatchOrders(
        submitter=normalize_address(submitter),
        taker_order=parlay_order_to_proto(taker_order),
        maker_orders=[parlay_order_to_proto(order) for order in maker_orders],
        taker_fill_amount=str(taker_fill_amount),
        maker_fill_amounts=[str(value) for value in maker_fill_amounts],
        surplus_recipient=normalize_address(surplus_recipient) if str(surplus_recipient).strip() else "",
    )
    if match_fee_bps is not None:
        payload.match_fee_bps = int(match_fee_bps)
    return payload


def build_msg_cancel_orders(signer: str, order_hashes: Sequence[str], principal: str = "") -> settlement_tx_pb2.MsgCancelOrders:
    return settlement_tx_pb2.MsgCancelOrders(
        signer=normalize_address(signer),
        principal=normalize_address(principal) if str(principal).strip() else "",
        order_hashes=[str(order_hash) for order_hash in order_hashes],
    )


def build_msg_invalidate_nonce(signer: str, min_valid_nonce: int | str, principal: str = "") -> settlement_tx_pb2.MsgInvalidateNonce:
    return settlement_tx_pb2.MsgInvalidateNonce(
        signer=normalize_address(signer),
        principal=normalize_address(principal) if str(principal).strip() else "",
        min_valid_nonce=normalize_uint256(min_valid_nonce, "min_valid_nonce"),
    )


def build_msg_approve_agent(principal: str, agent: str) -> settlement_tx_pb2.MsgApproveAgent:
    return settlement_tx_pb2.MsgApproveAgent(
        principal=normalize_address(principal),
        agent=normalize_address(agent),
    )


def build_msg_revoke_agent(principal: str, agent: str) -> settlement_tx_pb2.MsgRevokeAgent:
    return settlement_tx_pb2.MsgRevokeAgent(principal=normalize_address(principal), agent=normalize_address(agent))


def build_msg_pause_settlement(authority: str, paused: bool) -> settlement_tx_pb2.MsgPauseSettlement:
    return settlement_tx_pb2.MsgPauseSettlement(authority=normalize_address(authority), paused=bool(paused))


def build_msg_set_matcher_authorization(authority: str, matcher: str, allowed: bool) -> settlement_tx_pb2.MsgSetMatcherAuthorization:
    return settlement_tx_pb2.MsgSetMatcherAuthorization(
        authority=normalize_address(authority),
        matcher=normalize_address(matcher),
        allowed=bool(allowed),
    )


def build_msg_set_validator_set(authority: str, validators: Sequence[ValidatorSlot]) -> poa_tx_pb2.MsgSetValidatorSet:
    return poa_tx_pb2.MsgSetValidatorSet(
        authority=normalize_address(authority),
        validators=validator_slots_to_proto(validators),
    )


def build_msg_update_poa_admin(authority: str, new_admin: str) -> poa_tx_pb2.MsgUpdateAdmin:
    return poa_tx_pb2.MsgUpdateAdmin(authority=normalize_address(authority), new_admin=normalize_address(new_admin))
