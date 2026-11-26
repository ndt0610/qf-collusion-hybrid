// SPDX-License-Identifier: MIT
pragma solidity 0.8.30;

import {Ownable} from "@openzeppelin/contracts/access/Ownable.sol";
import {ReentrancyGuard} from "@openzeppelin/contracts/utils/ReentrancyGuard.sol";
import {MerkleProof} from "@openzeppelin/contracts/utils/cryptography/MerkleProof.sol";

contract MerkleQFVault is Ownable, ReentrancyGuard {
    uint256 public constant SCHEMA_VERSION = 1;
    address public constant NATIVE_ASSET = address(0);

    struct Round {
        bytes32 merkleRoot;
        uint64 claimDeadline;
        uint256 poolFunded;
        uint256 remaining;
        bool exists;
    }

    mapping(uint256 => Round) public rounds;
    mapping(uint256 => mapping(uint256 => bool)) public claimed;

    event RoundPublished(uint256 indexed roundId, bytes32 merkleRoot, uint256 poolFunded, uint64 claimDeadline);
    event Claimed(uint256 indexed roundId, uint256 indexed grantId, address indexed recipient, uint256 amount);
    event Swept(uint256 indexed roundId, address indexed to, uint256 amount);

    constructor() Ownable(msg.sender) {}

    function publishRound(uint256 roundId, bytes32 merkleRoot, uint64 claimDeadline)
        external payable onlyOwner
    {
        require(!rounds[roundId].exists, "round exists");
        require(merkleRoot != bytes32(0), "empty root");
        require(msg.value > 0, "empty funding");
        require(claimDeadline > block.timestamp, "deadline passed");
        rounds[roundId] = Round(merkleRoot, claimDeadline, msg.value, msg.value, true);
        emit RoundPublished(roundId, merkleRoot, msg.value, claimDeadline);
    }

    function claim(uint256 roundId, uint256 grantId, address recipient, uint256 amount,
                   bytes32[] calldata proof) external nonReentrant {
        Round storage round = rounds[roundId];
        require(round.exists, "round missing");
        require(block.timestamp <= round.claimDeadline, "deadline passed");
        require(!claimed[roundId][grantId], "already claimed");
        require(amount > 0, "zero amount");
        require(recipient != address(0), "zero recipient");
        require(round.remaining >= amount, "insufficient round balance");
        bytes32 leaf = keccak256(bytes.concat(keccak256(abi.encode(
            SCHEMA_VERSION, block.chainid, address(this), NATIVE_ASSET,
            roundId, grantId, recipient, amount
        ))));
        require(MerkleProof.verifyCalldata(proof, round.merkleRoot, leaf), "invalid proof");

        claimed[roundId][grantId] = true;
        round.remaining -= amount;
        (bool ok, ) = payable(recipient).call{value: amount}("");
        require(ok, "transfer failed");
        emit Claimed(roundId, grantId, recipient, amount);
    }

    function sweepUnclaimed(uint256 roundId, address to) external onlyOwner nonReentrant {
        Round storage round = rounds[roundId];
        require(round.exists, "round missing");
        require(block.timestamp > round.claimDeadline, "deadline active");
        require(to != address(0), "zero recipient");
        uint256 amount = round.remaining;
        round.remaining = 0;
        (bool ok, ) = payable(to).call{value: amount}("");
        require(ok, "sweep failed");
        emit Swept(roundId, to, amount);
    }
}
