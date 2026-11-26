// SPDX-License-Identifier: MIT
pragma solidity 0.8.30;

contract RejectEtherRecipient {
    receive() external payable { revert("reject ether"); }
}
