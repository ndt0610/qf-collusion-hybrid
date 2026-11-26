"""Phase 3 Python side of the payout bridge."""
import json
from decimal import Decimal
from pathlib import Path

from eth_utils import is_checksum_address

from qf_hybrid.allocation.core import apportion, normalize
from scripts.export_phase3_manifests import POOL_WEI, real_manifest, synthetic_manifest

ROOT = Path(__file__).resolve().parents[2]
VAULT = "0x1111111111111111111111111111111111111111"


def check_manifest(m, expected_n):
    assert m["chain_id"] == "31337"
    assert m["asset"]["kind"] == "native"
    assert m["asset"]["unit"] == "wei"
    assert m["asset"]["note"].endswith("not a USD-to-ETH conversion")
    assert len(m["payouts"]) == expected_n
    assert sum(int(p["amount"]) for p in m["payouts"]) + int(m["unallocated_amount"]) == POOL_WEI
    assert len({p["grant_id"] for p in m["payouts"]}) == expected_n
    assert all(is_checksum_address(p["recipient"]) and int(p["amount"]) > 0 for p in m["payouts"])


def test_wei_precision_and_1000_grant_manifest():
    scores = {str(i): Decimal(i) / Decimal("1e19") for i in range(1, 1001)}
    quotas, unallocated = normalize(scores, POOL_WEI)
    payouts = apportion(quotas, POOL_WEI, unallocated)
    assert sum(payouts.values()) == POOL_WEI
    check_manifest(synthetic_manifest(1000, VAULT), 1000)


def test_frozen_soft_base_real_manifests():
    frozen = json.loads((ROOT / "configs/heldout/frozen_mechanisms.json").read_text())
    source = json.loads((ROOT / "data/manifests/sources.json").read_text())
    hashes = {name: row["sha256"] for name, row in source["files"].items()}
    for round_id, expected_n in ((27, 46), (867, 142)):
        m = real_manifest(round_id, VAULT, frozen, hashes)
        check_manifest(m, expected_n)
        assert m["research"]["mechanism"] == "soft_base"
        assert m["research"]["source_chain_id"] == "42161"
