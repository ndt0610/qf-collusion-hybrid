"""Python verifier for OpenZeppelin StandardMerkleTree static eight-field leaves."""
from __future__ import annotations

from Crypto.Hash import keccak


def _keccak(data: bytes) -> bytes:
    digest = keccak.new(digest_bits=256)
    digest.update(data)
    return digest.digest()


def _uint(value: str | int) -> bytes:
    number = int(value)
    if not 0 <= number < 2**256:
        raise ValueError("uint256 out of range")
    return number.to_bytes(32, "big")


def _address(value: str) -> bytes:
    if not isinstance(value, str) or not value.startswith("0x") or len(value) != 42:
        raise ValueError("Invalid Ethereum address")
    try:
        address = bytes.fromhex(value[2:])
    except ValueError as error:
        raise ValueError("Invalid Ethereum address") from error
    return address.rjust(32, b"\0")


def compute_leaf_hash(*, schema_version: str, chain_id: str, vault_address: str,
                      asset_address: str, round_id: str, grant_id: str,
                      recipient: str, amount: str) -> str:
    """Compute keccak256(keccak256(abi.encode(eight static fields)))."""
    encoded = b"".join((
        _uint(schema_version), _uint(chain_id), _address(vault_address),
        _address(asset_address), _uint(round_id), _uint(grant_id),
        _address(recipient), _uint(amount),
    ))
    return "0x" + _keccak(_keccak(encoded)).hex()


def build_merkle_bundle(payouts: list[dict], *, round_id: str | int,
                        chain_id: str | int = "31337",
                        vault_address: str = "0x1111111111111111111111111111111111111111",
                        asset_address: str = "0x0000000000000000000000000000000000000000",
                        pool_amount: str | int | None = None,
                        metadata: dict | None = None) -> dict:
    """Build a StandardMerkleTree-compatible root and per-leaf proofs in Python.

    OpenZeppelin sorts leaf hashes, then fills a complete array tree backwards.
    The resulting proof order and root match @openzeppelin/merkle-tree.
    """
    if not payouts:
        raise ValueError("At least one positive payout is required")
    base = {"schema_version": "1", "chain_id": str(chain_id),
            "vault_address": vault_address, "asset_address": asset_address,
            "round_id": str(round_id)}
    normalized = []
    seen = set()
    for payout in payouts:
        grant_id = str(payout["grant_id"])
        amount = str(payout["amount"])
        if int(amount) <= 0 or grant_id in seen:
            raise ValueError("Payouts require unique grant IDs and positive integer wei")
        seen.add(grant_id)
        row = {"grant_id": grant_id, "recipient": payout["recipient"], "amount": amount}
        leaf = bytes.fromhex(compute_leaf_hash(**base, **row)[2:])
        if row["recipient"].lower() == "0x" + "0" * 40:
            raise ValueError("Payout recipient must not be the zero address")
        normalized.append((leaf, row))
    normalized.sort(key=lambda item: item[0])
    count = len(normalized)
    tree = [b""] * (2 * count - 1)
    tree_indices = {}
    for index, (leaf, row) in enumerate(normalized):
        node_index = len(tree) - index - 1
        tree[node_index] = leaf
        tree_indices[row["grant_id"]] = node_index
    for index in range(len(tree) - count - 1, -1, -1):
        left, right = tree[2 * index + 1], tree[2 * index + 2]
        tree[index] = _keccak(b"".join(sorted((left, right))))
    leaves = []
    for _, row in sorted(normalized, key=lambda item: int(item[1]["grant_id"])):
        index = tree_indices[row["grant_id"]]
        proof = []
        while index > 0:
            sibling_index = index + 1 if index % 2 else index - 1
            proof.append("0x" + tree[sibling_index].hex())
            index = (index - 1) // 2
        leaves.append({**row, "proof": proof})
    paid = sum(int(row["amount"]) for row in leaves)
    pool = int(pool_amount) if pool_amount is not None else paid
    if pool < paid:
        raise ValueError("Payouts exceed pool")
    bundle = {"root": "0x" + tree[0].hex(), **base, "pool_amount": str(pool),
              "unallocated_amount": str(pool - paid), "leaves": leaves}
    if metadata:
        bundle["demo_metadata"] = dict(metadata)
    return bundle


def verify_merkle_proof_with_trace(bundle: dict, grant_id: str | int, *,
                                   amount_override: str | int | None = None,
                                   recipient_override: str | None = None,
                                   field_overrides: dict | None = None) -> dict:
    """Return byte-exact validity and each sorted-pair step, including first divergence."""
    leaf = next((row for row in bundle["leaves"] if str(row["grant_id"]) == str(grant_id)), None)
    if leaf is None:
        raise ValueError("grant_id absent from bundle")
    fields = {key: bundle[key] for key in ("schema_version", "chain_id", "vault_address",
                                        "asset_address", "round_id")}
    fields.update({key: leaf[key] for key in ("grant_id", "recipient", "amount")})
    if amount_override is not None:
        fields["amount"] = str(amount_override)
    if recipient_override is not None:
        fields["recipient"] = recipient_override
    if field_overrides:
        fields.update(field_overrides)
    current = bytes.fromhex(compute_leaf_hash(**fields)[2:])
    original = bytes.fromhex(compute_leaf_hash(
        **{**{key: bundle[key] for key in ("schema_version", "chain_id", "vault_address",
                                         "asset_address", "round_id")},
           **{key: leaf[key] for key in ("grant_id", "recipient", "amount")}})[2:])
    trace = [{"level": 0, "node": "0x" + current.hex(), "expected_node": "0x" + original.hex(),
              "sibling": None, "matches_original": current == original}]
    for level, sibling_hex in enumerate(leaf["proof"], 1):
        sibling = bytes.fromhex(sibling_hex[2:])
        current = _keccak(b"".join(sorted((current, sibling))))
        original = _keccak(b"".join(sorted((original, sibling))))
        trace.append({"level": level, "node": "0x" + current.hex(),
                      "expected_node": "0x" + original.hex(), "sibling": sibling_hex,
                      "matches_original": current == original})
    expected_root = bundle["root"]
    computed_root = "0x" + current.hex()
    mismatch = next((row["level"] for row in trace if not row["matches_original"]), None)
    return {"valid": computed_root.lower() == expected_root.lower(),
            "computed_root": computed_root, "expected_root": expected_root,
            "first_divergence_level": mismatch, "trace": trace, "fields": fields}
