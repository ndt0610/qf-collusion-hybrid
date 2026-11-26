// SPDX-License-Identifier: MIT
pragma solidity 0.8.30;

import {Ownable} from "@openzeppelin/contracts/access/Ownable.sol";
import {ReentrancyGuard} from "@openzeppelin/contracts/utils/ReentrancyGuard.sol";

contract NaiveStorageQFVault is Ownable, ReentrancyGuard {
    struct Round {
        uint64 claimDeadline;
        uint256 poolFunded;
        uint256 remaining;
        uint256 assigned;
        bool exists;
        bool finalized;
    }
    struct Payout {
        address recipient;
        uint256 amount;
        bool exists;
    }

    mapping(uint256 => Round) public rounds;
    mapping(uint256 => mapping(uint256 => Payout)) public payouts;
    mapping(uint256 => mapping(uint256 => bool)) public claimed;

    event RoundInitialized(uint256 indexed roundId, uint256 poolFunded, uint64 claimDeadline);
    event Claimed(uint256 indexed roundId, uint256 indexed grantId, address indexed recipient, uint256 amount);
    event Swept(uint256 indexed roundId, address indexed to, uint256 amount);

    constructor() Ownable(msg.sender) {}

    function initRound(uint256 roundId, uint64 claimDeadline) external payable onlyOwner {
        require(!rounds[roundId].exists, "round exists");
        require(msg.value > 0, "empty funding");
        require(claimDeadline > block.timestamp, "deadline passed");
        rounds[roundId] = Round(claimDeadline, msg.value, msg.value, 0, true, false);
        emit RoundInitialized(roundId, msg.value, claimDeadline);
    }

    function setPayoutsBatch(uint256 roundId, uint256[] calldata grantIds,
                             address[] calldata recipients, uint256[] calldata amounts)
        external onlyOwner
    {
        Round storage round = rounds[roundId];
        require(round.exists && !round.finalized, "round not writable");
        require(block.timestamp <= round.claimDeadline, "deadline passed");
        require(grantIds.length > 0 && grantIds.length == recipients.length &&
                grantIds.length == amounts.length, "batch length");
        for (uint256 i = 0; i < grantIds.length; ++i) {
            require(!payouts[roundId][grantIds[i]].exists, "duplicate grant");
            require(recipients[i] != address(0) && amounts[i] > 0, "invalid payout");
            round.assigned += amounts[i];
            require(round.assigned <= round.poolFunded, "over-assigned");
            payouts[roundId][grantIds[i]] = Payout(recipients[i], amounts[i], true);
        }
    }

    function finalizeRound(uint256 roundId) external onlyOwner {
        Round storage round = rounds[roundId];
        require(round.exists && !round.finalized, "round not writable");
        require(block.timestamp <= round.claimDeadline, "deadline passed");
        round.finalized = true;
    }

    function claim(uint256 roundId, uint256 grantId) external nonReentrant {
        Round storage round = rounds[roundId];
        require(round.exists && round.finalized, "round not finalized");
        require(block.timestamp <= round.claimDeadline, "deadline passed");
        require(!claimed[roundId][grantId], "already claimed");
        Payout storage payout = payouts[roundId][grantId];
        require(payout.exists && payout.amount > 0, "payout missing");
        require(round.remaining >= payout.amount, "insufficient round balance");
        claimed[roundId][grantId] = true;
        round.remaining -= payout.amount;
        (bool ok, ) = payable(payout.recipient).call{value: payout.amount}("");
        require(ok, "transfer failed");
        emit Claimed(roundId, grantId, payout.recipient, payout.amount);
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
