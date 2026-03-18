from __future__ import annotations

from dataclasses import dataclass

from predchain_sdk_v2 import Order, PredchainRelayerClient, TxSubmission


@dataclass(slots=True)
class ReadySettlement:
    taker_order: Order
    maker_orders: list[Order]
    taker_fill_amount: str
    maker_fill_amounts: list[str]
    surplus_recipient: str = ""


def settle_ready_match(relayer: PredchainRelayerClient, ready: ReadySettlement) -> TxSubmission:
    """
    Example orderbook handoff.

    The orderbook has already decided the match and already has signed orders.
    The relayer SDK only needs to submit the outer native chain tx.
    """

    return relayer.match_orders(
        taker_order=ready.taker_order,
        maker_orders=ready.maker_orders,
        taker_fill_amount=ready.taker_fill_amount,
        maker_fill_amounts=ready.maker_fill_amounts,
        surplus_recipient=ready.surplus_recipient,
        broadcast_mode="BROADCAST_MODE_SYNC",
    )


def handle_submission(submission: TxSubmission) -> None:
    if submission.accepted:
        print(f"accepted tx {submission.tx_hash} status={submission.status}")
        return
    print(f"rejected tx {submission.tx_hash} log={submission.broadcast_raw_log}")


def main() -> None:
    relayer = PredchainRelayerClient(
        api_url="http://46.62.232.134:1317",
        rpc_url="http://46.62.232.134:26657",
        signer_address="0xRELAYER",
        private_key_hex="RELAYER_PRIVATE_KEY_HEX",
    )
    relayer.sync_signer_state()

    ready = ReadySettlement(
        taker_order=Order(
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
        ),
        maker_orders=[
            Order(
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
        ],
        taker_fill_amount="500000",
        maker_fill_amounts=["1000000"],
    )

    submission = settle_ready_match(relayer, ready)
    handle_submission(submission)


if __name__ == "__main__":
    main()
