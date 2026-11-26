"""Bind frozen soft_base payouts to an independently denominated local EVM pool."""
import argparse
import hashlib
import json
from decimal import Decimal
from pathlib import Path

from eth_utils import to_checksum_address

from qf_hybrid.allocation.core import apportion, manifest, normalize
from qf_hybrid.data.rounds import load_round
from qf_hybrid.experiments.trials import WorldCache
from qf_hybrid.mechanisms.core import lambdas_for_branch, soft_discounting

ROOT = Path(__file__).resolve().parents[1]
POOL_WEI = 100 * 10**18
ZERO = "0x" + "0"*40
ASSET_NOTE = "Local EVM test pool proportional to research allocation; not a USD-to-ETH conversion"


def canonical_hash(value):
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def recipient_for(round_id, project):
    digest = hashlib.sha256(f"phase3-recipient:{round_id}:{project}".encode()).digest()
    return to_checksum_address("0x" + digest[-20:].hex())


def checked_manifest(round_id, vault, payouts, recipients, data_hash, config_hash, research):
    out = manifest(round_id=round_id, chain_id=31337, vault=vault, asset_address=ZERO,
                   decimals=18, pool_amount=POOL_WEI, payouts=payouts, recipients=recipients,
                   data_sha256=data_hash, config_sha256=config_hash, unallocated=0)
    out["vault_address"] = to_checksum_address(out["vault_address"])
    out["asset"]["address"] = to_checksum_address(out["asset"]["address"])
    out["asset"]["note"] = ASSET_NOTE
    for row in out["payouts"]:
        row["recipient"] = to_checksum_address(row["recipient"])
    out["research"] = research
    return out


def real_manifest(round_id, vault, frozen, hashes):
    loaded = load_round(ROOT/"data/raw", "42161", str(round_id), hashes)
    selected = frozen["selected"]["0.05"]["soft_base"]
    key = tuple(selected["graph_key"])
    world = WorldCache(loaded.contributions, keys=[key], seed=frozen["louvain_seed"])
    matrix = world.feature_matrices[key]
    lambdas = lambdas_for_branch(matrix.features, "soft_base", selected["beta"], matrix.n_donors)
    scores = soft_discounting(loaded.contributions, matrix.communities, lambdas)
    quotas, unallocated = normalize(scores, POOL_WEI)
    if unallocated:
        raise ValueError("Real round has no positive matching score")
    projects = sorted(scores)
    grant_ids = {project: str(i+1) for i, project in enumerate(projects)}
    payouts = apportion({grant_ids[p]: quotas[p] for p in projects}, POOL_WEI)
    if any(value <= 0 for value in payouts.values()):
        raise ValueError("A real project has zero payout; cannot claim all projects")
    recipients = {grant_ids[p]: recipient_for(round_id, p) for p in projects}
    data_hash = canonical_hash([[u, p, str(amount)] for (u, p), amount in sorted(loaded.contributions.items())])
    config_hash = canonical_hash({"mechanism": "soft_base", "selected": selected,
                                  "frozen_protocol_sha256": frozen["protocol_sha256"]})
    research = {"kind": "real_background", "source_chain_id": "42161", "source_round_id": str(round_id),
                "mechanism": "soft_base", "fixed_research_pool_usd": "100000",
                "evm_pool_is_independent": True, "project_count": len(projects),
                "source_parquet_sha256": hashes["donations.parquet"],
                "grant_project_map": {grant_ids[p]: p for p in projects}}
    return checked_manifest(round_id, vault, payouts, recipients, data_hash, config_hash, research)


def synthetic_manifest(n, vault):
    # Positive deterministic weights; exact wei distribution uses the Phase 1 allocator.
    weights = {str(i): Decimal(n+1-i) for i in range(1, n+1)}
    quotas, unallocated = normalize(weights, POOL_WEI)
    assert unallocated == 0
    payouts = apportion(quotas, POOL_WEI)
    recipients = {grant: recipient_for(10000+n, grant) for grant in weights}
    return checked_manifest(10000+n, vault, payouts, recipients,
                            canonical_hash({"synthetic_n": n, "weights": "descending_integer"}),
                            canonical_hash({"benchmark": "phase3", "n": n, "pool_wei": str(POOL_WEI)}),
                            {"kind": "synthetic_benchmark", "project_count": n,
                             "weight_rule": "descending_integer", "evm_pool_is_independent": True})


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--vault", required=True, help="Deployed MerkleQFVault address")
    parser.add_argument("--kind", choices=("all", "real", "synthetic"), default="all")
    parser.add_argument("--synthetic-n", type=int, choices=(10, 50, 100, 250, 500, 1000),
                        help="Emit only one benchmark size")
    parser.add_argument("--output", type=Path, default=ROOT/"results/runs/phase3/manifests")
    args = parser.parse_args()
    vault = to_checksum_address(args.vault)
    args.output.mkdir(parents=True, exist_ok=True)
    artifacts = []
    if args.kind in ("all", "real"):
        frozen = json.loads((ROOT/"configs/heldout/frozen_mechanisms.json").read_text())
        source = json.loads((ROOT/"data/manifests/sources.json").read_text())
        hashes = {name: row["sha256"] for name, row in source["files"].items()}
        for rid in (27, 867):
            artifacts.append((f"real_{rid}.json", real_manifest(rid, vault, frozen, hashes)))
    if args.kind in ("all", "synthetic"):
        for n in ((args.synthetic_n,) if args.synthetic_n else (10, 50, 100, 250, 500, 1000)):
            artifacts.append((f"synthetic_{n}.json", synthetic_manifest(n, vault)))
    for name, value in artifacts:
        (args.output/name).write_text(json.dumps(value, sort_keys=True, indent=2)+"\n", encoding="utf-8")
        print(f"{name}: {len(value['payouts'])} payouts, {value['pool_amount']} wei", flush=True)


if __name__ == "__main__":
    main()
