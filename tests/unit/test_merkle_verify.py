"""Cross-check Python Keccak against all OpenZeppelin-generated demo proofs."""
import json
from pathlib import Path

import pytest

from qf_hybrid.allocation.core import manifest
from qf_hybrid.ui.merkle_verify import build_merkle_bundle, verify_merkle_proof_with_trace


ROOT = Path(__file__).resolve().parents[2]


@pytest.mark.parametrize("round_id,count", [(27, 46), (867, 142)])
def test_all_openzeppelin_leaves(round_id, count):
    bundle = json.loads((ROOT / f"results/gas/demo_merkle_round_{round_id}.json").read_text())
    assert len(bundle["leaves"]) == count
    for leaf in bundle["leaves"]:
        result = verify_merkle_proof_with_trace(bundle, leaf["grant_id"])
        assert result["valid"]
        assert result["computed_root"].lower() == bundle["root"].lower()
        assert result["first_divergence_level"] is None
        for tampered in (
            {"amount_override": int(leaf["amount"]) + 1},
            {"recipient_override": "0x0000000000000000000000000000000000000001"},
            {"field_overrides": {"round_id": str(int(bundle["round_id"]) + 1)}},
        ):
            altered = verify_merkle_proof_with_trace(bundle, leaf["grant_id"], **tampered)
            assert not altered["valid"]
            assert altered["first_divergence_level"] == 0
            assert all(not step["matches_original"] for step in altered["trace"])


@pytest.mark.parametrize("round_id", [27, 867])
def test_python_builder_reproduces_openzeppelin_root_and_proofs(round_id):
    source = json.loads((ROOT / f"results/gas/demo_merkle_round_{round_id}.json").read_text())
    built = build_merkle_bundle(source["leaves"], round_id=source["round_id"],
                                chain_id=source["chain_id"],
                                vault_address=source["vault_address"],
                                asset_address=source["asset_address"],
                                pool_amount=source["pool_amount"])
    assert built["root"] == source["root"]
    assert built["leaves"] == source["leaves"]
    assert built["unallocated_amount"] == source["unallocated_amount"]


def test_python_builder_rejects_zero_recipient():
    with pytest.raises(ValueError, match="zero address"):
        build_merkle_bundle([{"grant_id": "1",
                              "recipient": "0x0000000000000000000000000000000000000000",
                              "amount": "1"}], round_id=1)


def test_python_manifest_rejects_zero_payout_recipient_but_allows_native_asset():
    kwargs = dict(round_id=1, chain_id=31337,
                  vault="0x1111111111111111111111111111111111111111",
                  asset_address="0x0000000000000000000000000000000000000000",
                  decimals=18, pool_amount=1, payouts={"1": 1},
                  recipients={"1": "0x0000000000000000000000000000000000000000"},
                  data_sha256="a" * 64, config_sha256="b" * 64)
    with pytest.raises(ValueError, match="Zero payout recipient"):
        manifest(**kwargs)
    kwargs["recipients"]["1"] = "0x2222222222222222222222222222222222222222"
    assert manifest(**kwargs)["asset"]["kind"] == "native"
