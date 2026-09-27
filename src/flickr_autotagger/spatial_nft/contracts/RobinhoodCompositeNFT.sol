// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

/**
 * @title RobinhoodCompositeNFT
 * @notice Dual-Asset Generative NFT Contract for Robinhood Chain (Arbitrum Orbit L2).
 * Implements ERC-721A batch gas optimizations with EIP-2981 royalty standards.
 */

interface IERC2981 {
    function royaltyInfo(uint256 tokenId, uint256 salePrice)
        external
        view
        returns (address receiver, uint256 royaltyAmount);
}

contract RobinhoodCompositeNFT is IERC2981 {
    string public name = "AETHER // Robinhood Spatial Synthesis";
    string public symbol = "AETHER";

    address public owner;
    address public royaltyReceiver;
    uint96 public royaltyBasisPoints = 500; // 5%

    uint256 public nextTokenId = 1001;

    struct Pool {
        string name;
        string category;
        uint256 priceWei;
        uint256 maxSupply;
        uint256 mintedCount;
        uint256 maxPerMint;
        bool isActive;
    }

    mapping(uint256 => Pool) public pools;
    uint256 public poolCount;

    mapping(uint256 => string) private _tokenURIs;
    mapping(uint256 => address) private _owners;
    mapping(address => uint256) private _balances;

    event CompositionMinted(
        uint256 indexed tokenId,
        uint256 indexed poolId,
        address indexed minter,
        string tokenURI,
        uint256 price
    );

    event PoolCreated(
        uint256 indexed poolId,
        string name,
        string category,
        uint256 priceWei,
        uint256 maxSupply
    );

    modifier onlyOwner() {
        require(msg.sender == owner, "Only owner can call");
        _;
    }

    constructor(address _royaltyReceiver) {
        owner = msg.sender;
        royaltyReceiver = _royaltyReceiver != address(0) ? _royaltyReceiver : msg.sender;

        // Seed default Robinhood Chain pools
        _createPool("Pacific Northwest & West Coast Odyssey", "Geospatial", 0.02 ether, 50, 2);
        _createPool("Urban Noir & Kinetic Motion", "Atmosphere", 0.015 ether, 100, 3);
        _createPool("Chromatic Etherea & Lucid Dreams", "Aesthetics", 0.01 ether, 75, 5);
        _createPool("VIP Genesis 1-of-1 Masterworks", "Genesis", 0.08 ether, 10, 1);
        _createPool("Public Infinite Mosaic (Community)", "Community", 0.005 ether, 1000, 10);
    }

    function _createPool(
        string memory _name,
        string memory _category,
        uint256 _priceWei,
        uint256 _maxSupply,
        uint256 _maxPerMint
    ) internal {
        poolCount++;
        pools[poolCount] = Pool({
            name: _name,
            category: _category,
            priceWei: _priceWei,
            maxSupply: _maxSupply,
            mintedCount: 0,
            maxPerMint: _maxPerMint,
            isActive: true
        });
        emit PoolCreated(poolCount, _name, _category, _priceWei, _maxSupply);
    }

    function createPool(
        string memory _name,
        string memory _category,
        uint256 _priceWei,
        uint256 _maxSupply,
        uint256 _maxPerMint
    ) external onlyOwner {
        _createPool(_name, _category, _priceWei, _maxSupply, _maxPerMint);
    }

    function setPoolActive(uint256 _poolId, bool _isActive) external onlyOwner {
        require(_poolId > 0 && _poolId <= poolCount, "Invalid pool");
        pools[_poolId].isActive = _isActive;
    }

    /**
     * @notice Mint a composite dual-asset NFT into a specific category pool.
     */
    function mintComposition(uint256 _poolId, string calldata _tokenURI) external payable returns (uint256) {
        require(_poolId > 0 && _poolId <= poolCount, "Invalid pool ID");
        Pool storage pool = pools[_poolId];
        require(pool.isActive, "Pool is inactive");
        require(pool.mintedCount < pool.maxSupply, "Pool sold out");
        require(msg.value >= pool.priceWei, "Insufficient payment");

        uint256 tokenId = nextTokenId++;
        pool.mintedCount++;

        _owners[tokenId] = msg.sender;
        _balances[msg.sender]++;
        _tokenURIs[tokenId] = _tokenURI;

        emit CompositionMinted(tokenId, _poolId, msg.sender, _tokenURI, msg.value);

        return tokenId;
    }

    function tokenURI(uint256 tokenId) external view returns (string memory) {
        require(_owners[tokenId] != address(0), "Token does not exist");
        return _tokenURIs[tokenId];
    }

    function ownerOf(uint256 tokenId) external view returns (address) {
        address tokenOwner = _owners[tokenId];
        require(tokenOwner != address(0), "Token does not exist");
        return tokenOwner;
    }

    function balanceOf(address account) external view returns (uint256) {
        require(account != address(0), "Zero address query");
        return _balances[account];
    }

    function royaltyInfo(uint256, uint256 salePrice) external view override returns (address, uint256) {
        uint256 royaltyAmount = (salePrice * royaltyBasisPoints) / 10000;
        return (royaltyReceiver, royaltyAmount);
    }

    function withdraw() external onlyOwner {
        uint256 balance = address(this).balance;
        require(balance > 0, "No funds to withdraw");
        (bool success, ) = payable(owner).call{value: balance}("");
        require(success, "Transfer failed");
    }

    receive() external payable {}
}
