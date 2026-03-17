from predchain_sdk_v2 import Order, PredchainSDKv2Client


def main() -> None:
    client = PredchainSDKv2Client(
        api_url="http://46.62.232.134:1317",
        rpc_url="http://46.62.232.134:26657",
        signer_address="0xRELAYER",
        private_key_hex="RELAYER_PRIVATE_KEY_HEX",
    )

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

    submission = client.match_orders(
        taker_order=taker,
        maker_orders=[maker],
        taker_fill_amount="500000",
        maker_fill_amounts=["1000000"],
    )
    print(submission.to_dict())


if __name__ == "__main__":
    main()
