from predchain_sdk_v2 import ParlayLeg, PredchainRelayerClient


def main() -> None:
    client = PredchainRelayerClient(
        api_url="http://46.62.232.134:1317",
        rpc_url="http://46.62.232.134:26657",
        signer_address="0xADMIN_RELAYER",
        private_key_hex="ADMIN_RELAYER_PRIVATE_KEY_HEX",
    )

    # Query current admins/authorities before taking any market action.
    print("authorities:", client.authorities())
    print("settlement params:", client.settlement_params())

    # Inspect existing registry state.
    print("markets page:", client.markets(limit=5, offset=0))

    # Create a normal market.
    created = client.create_market(
        question="Will team A win?",
        metadata_uri="ipfs://market/team-a-win",
        broadcast_mode="BROADCAST_MODE_SYNC",
    )
    print("create market:", created.to_dict())

    # Create a parlay market from existing underlying markets.
    parlay = client.create_parlay_market(
        legs=[
            ParlayLeg(market_id=11, required_outcome="YES"),
            ParlayLeg(market_id=12, required_outcome="YES"),
        ],
        broadcast_mode="BROADCAST_MODE_SYNC",
    )
    print("create parlay:", parlay.to_dict())

    # Extend an existing neg-risk group with new market ids.
    update = client.update_neg_risk_group(
        group_id=3,
        add_market_ids=[11, 12],
        title="Expanded group",
        metadata_uri="ipfs://group/expanded",
        broadcast_mode="BROADCAST_MODE_SYNC",
    )
    print("update neg-risk group:", update.to_dict())


if __name__ == "__main__":
    main()
