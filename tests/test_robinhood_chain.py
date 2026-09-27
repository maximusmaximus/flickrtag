"""Unit tests for Robinhood Chain (Arbitrum Orbit L2) integration."""

from flickr_autotagger.spatial_nft.backend.robinhood_chain import (
    ROBINHOOD_MAINNET,
    ROBINHOOD_TESTNET,
    CONTRACT_CONFIG,
    COMPOSITE_NFT_ABI,
    RobinhoodChainClient,
    robinhood_client,
)


def test_robinhood_constants():
    """Verify official Robinhood Chain parameters."""
    assert ROBINHOOD_MAINNET["chain_id"] == 4663
    assert ROBINHOOD_MAINNET["hex_chain_id"] == "0x1237"
    assert ROBINHOOD_MAINNET["symbol"] == "ETH"
    assert "chain.robinhood.com" in ROBINHOOD_MAINNET["rpc_url"]
    assert "explorer.chain.robinhood.com" in ROBINHOOD_MAINNET["explorer_url"]


def test_robinhood_client_status():
    """Verify status method returns required network parameters."""
    client = RobinhoodChainClient()
    status = client.get_status()

    assert status["chain_id"] == 4663
    assert status["chain_name"] == "Robinhood Chain"
    assert status["symbol"] == "ETH"
    assert status["block_number"] > 0
    assert status["gas_price_gwei"] >= 0.0
    assert status["is_online"] is True


def test_robinhood_verify_tx():
    """Verify transaction verification and explorer link generation."""
    client = RobinhoodChainClient()
    test_hash = "0x4663a7b819f2c38d21c33a4ba99d04a999b81f24"
    result = client.verify_tx(test_hash)

    assert result["verified"] is True
    assert "explorer_link" in result
    assert test_hash in result["explorer_link"]


def test_composite_nft_abi():
    """Verify smart contract ABI contains necessary mint and royalty methods."""
    abi_names = [item["name"] for item in COMPOSITE_NFT_ABI if "name" in item]
    assert "mintComposition" in abi_names
    assert "tokenURI" in abi_names
    assert "totalSupply" in abi_names
    assert "royaltyInfo" in abi_names
    assert "CompositionMinted" in abi_names
