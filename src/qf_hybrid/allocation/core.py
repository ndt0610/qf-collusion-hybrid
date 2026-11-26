"""Pool normalization, exact integer apportionment, and EVM manifest."""
from decimal import Decimal, ROUND_FLOOR, localcontext


def normalize(scores, pool):
    budget = Decimal(str(pool))
    if budget < 0:
        raise ValueError("Negative pool")
    raw = {p: Decimal(str(x)) for p, x in scores.items()}
    if any(not x.is_finite() or x < 0 for x in raw.values()):
        raise ValueError("Invalid raw score")
    total = sum(raw.values(), Decimal(0))
    if total == 0:
        return {p: Decimal(0) for p in raw}, budget
    # Wei-scale pools need substantially more than Decimal's default 28 digits.
    with localcontext() as context:
        context.prec = max(80, len(budget.as_tuple().digits)+40)
        return {p: budget*x/total for p, x in raw.items()}, Decimal(0)


def apportion(quotas, pool_amount, unallocated=0):
    pool = int(pool_amount)
    remaining = int(unallocated)
    if pool < 0 or remaining < 0 or remaining > pool:
        raise ValueError("Invalid pool or unallocated")
    q = {str(key): Decimal(str(value)) for key, value in quotas.items()}
    if any(not x.is_finite() or x < 0 for x in q.values()):
        raise ValueError("Invalid quota")
    target = pool-remaining
    with localcontext() as context:
        context.prec = max(80, len(str(pool))+40)
        if abs(sum(q.values(), Decimal(0))-Decimal(target)) > Decimal("1e-20"):
            raise ValueError("Quotas do not sum to distributable pool")
    payouts = {p: int(x.to_integral_value(rounding=ROUND_FLOOR)) for p, x in q.items()}
    leftover = target-sum(payouts.values())
    if leftover < 0 or leftover > len(q):
        raise ValueError("Invalid rounding remainder")
    for p in sorted(q, key=lambda p: (-(q[p]-payouts[p]), int(p)) )[:leftover]:
        payouts[p] += 1
    assert sum(payouts.values())+remaining == pool
    return payouts


def manifest(*, round_id, chain_id, vault, asset_address, decimals, pool_amount,
             payouts, recipients, data_sha256, config_sha256, unallocated=0, schema_version=1):
    """Create the JSON data for StandardMerkleTree's eight ABI fields.

    `vault` is required so the caller must deploy first; this does not build the tree.
    """
    import re
    def address(value):
        if not re.fullmatch(r"0x[0-9a-fA-F]{40}", value):
            raise ValueError("Invalid address")
        return value.lower()
    if any(not re.fullmatch(r"[0-9a-fA-F]{64}", x) for x in (data_sha256, config_sha256)):
        raise ValueError("Invalid SHA-256")
    for value in (round_id, chain_id, pool_amount, unallocated, schema_version):
        if not 0 <= int(value) < 2**256:
            raise ValueError("Invalid uint256")
    if set(payouts) != set(recipients) or sum(payouts.values())+int(unallocated) != int(pool_amount):
        raise ValueError("Payouts/recipients/pool mismatch")
    rows = []
    for grant in sorted(payouts, key=lambda x: int(x)):
        amount = int(payouts[grant])
        if not 0 <= amount < 2**256 or not 0 <= int(grant) < 2**256:
            raise ValueError("Invalid grant or payout")
        recipient = address(recipients[grant])
        if int(recipient, 16) == 0:
            raise ValueError("Zero payout recipient")
        rows.append({"grant_id": str(int(grant)), "recipient": recipient, "amount": str(amount)})
    if len({r["grant_id"] for r in rows}) != len(rows):
        raise ValueError("Duplicate grant ID")
    return {"schema_version": str(schema_version), "round_id": str(round_id),
            "chain_id": str(chain_id), "vault_address": address(vault),
            "asset": {"kind": "native" if int(asset_address, 16) == 0 else "erc20",
                      "address": address(asset_address), "decimals": int(decimals),
                      "unit": "wei" if int(asset_address, 16) == 0 else "token-base-unit"},
            "pool_amount": str(pool_amount), "unallocated_amount": str(unallocated),
            "data_sha256": data_sha256.lower(), "config_sha256": config_sha256.lower(),
            "leaf_abi_types": ["uint256","uint256","address","address","uint256","uint256","address","uint256"],
            "payouts": rows}
