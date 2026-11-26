// SPDX-License-Identifier: MIT
pragma solidity 0.8.30;

interface IMerkleQFVault {
    function claim(uint256 roundId, uint256 grantId, address recipient, uint256 amount,
                   bytes32[] calldata proof) external;
}

contract ReentrantRecipient {
    IMerkleQFVault public vault;
    uint256 public roundId;
    uint256 public grantId;
    uint256 public amount;
    bytes32[] private proof;

    function configure(address vault_, uint256 roundId_, uint256 grantId_, uint256 amount_,
                       bytes32[] calldata proof_) external {
        vault = IMerkleQFVault(vault_);
        roundId = roundId_;
        grantId = grantId_;
        amount = amount_;
        proof = proof_;
    }

    receive() external payable {
        vault.claim(roundId, grantId, address(this), amount, proof);
    }
}
