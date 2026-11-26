"""Summarize executed EVM receipts; never substitute estimateGas."""
import csv
import json
from pathlib import Path
from statistics import mean, median

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

ROOT = Path(__file__).resolve().parents[1]
GAS = ROOT / "results/gas"
FIGURES = ROOT / "results/figures"
RATIOS = (0.25, 0.5, 1.0)


def summarize_row(raw):
    n = raw["n"]
    m, s = raw["merkle"], raw["naive"]
    mc = [int(x) for x in m["claim_gas_receipts"]]
    sc = [int(x) for x in s["claim_gas_receipts"]]
    assert len(mc) == len(sc) == n, "Full-claim benchmark required"
    mp = int(m["publish_gas"])
    sp = int(s["init_gas"]) + sum(map(int, s["batch_gas_receipts"])) + int(s["finalize_gas"])
    assert len(s["batch_gas_receipts"]) == (n + 99) // 100
    row = {"n": n, "naive_batches": len(s["batch_gas_receipts"]),
           "merkle_deploy_gas": int(m["deploy_gas"]), "naive_deploy_gas": int(s["deploy_gas"]),
           "merkle_publish_gas": mp, "naive_publish_gas": sp,
           "publish_saving_pct": 100 * (sp-mp) / sp}
    for prefix, claims in (("merkle", mc), ("naive", sc)):
        row.update({f"{prefix}_claim_min": min(claims),
                    f"{prefix}_claim_median": median(claims),
                    f"{prefix}_claim_mean": mean(claims),
                    f"{prefix}_claim_max": max(claims)})
    for ratio in RATIOS:
        count = int(n * ratio + 0.999999999)
        suffix = f"{int(ratio*100)}pct"
        ml = mp + sum(mc[:count])
        sl = sp + sum(sc[:count])
        row.update({f"claim_count_{suffix}": count,
                    f"merkle_lifecycle_{suffix}": ml,
                    f"naive_lifecycle_{suffix}": sl,
                    f"lifecycle_saving_{suffix}": 100*(sl-ml)/sl})
    # Earliest executed claim count at which Merkle's total gas is at most naive's.
    diff = mp-sp
    breakeven = 0 if diff <= 0 else None
    if breakeven is None:
        for k, (mg, sg) in enumerate(zip(mc, sc), 1):
            diff += mg-sg
            if diff <= 0:
                breakeven = k
                break
    row["merkle_breakeven_claim_count"] = breakeven if breakeven is not None else "not_reached"
    return row


def main():
    raw = json.loads((GAS / "phase3_gas_receipts.json").read_text())
    rows = [summarize_row(item) for item in raw["rows"]]
    assert [r["n"] for r in rows] == [10, 50, 100, 250, 500, 1000]
    with (GAS / "phase3_gas_benchmark.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    meta = {**raw["meta"], "receipt_source": "Hardhat local EVM transaction receipt.gasUsed",
            "claim_method": "all N claims executed on each vault for every scale",
            "lifecycle_method": "publish receipts plus first ceil(ratio*N) actual claim receipts; deploy separate",
            "admin_gas": "deployment and publishing (naive includes init, all batches, finalize)",
            "claimant_gas": "permissionless claim caller; owner may also call but benchmark isolates claim transactions",
            "cost_scope": "gas units on local Cancun EVM, no mainnet USD conversion",
            "merkle_storage_scope": "one root per round plus claimed mapping entries for executed claims"}
    (GAS / "phase3_evm_meta.json").write_text(json.dumps(meta, indent=2)+"\n")

    lines = ["# Phase 3 EVM gas benchmark", "",
             "All entries are executed `receipt.gasUsed` on Hardhat 3, chain 31337, Cancun, solc 0.8.30, optimizer 200. Deployment is separate from lifecycle. Naive batches contain at most 100 payouts. All claims were executed at every N; lifecycle uses the first `ceil(ratio × N)` actual claim receipts. Savings = `(Naive − Merkle) / Naive`; negative means Merkle costs more.", "",
             "| N | Batches | Deploy M / S | Publish M / S | Publish saving | Claim mean M / S | Claim max M / S | Life 25% M / S (saving) | Life 50% M / S (saving) | Life 100% M / S (saving) | Merkle break-even claims |",
             "|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|"]
    for r in rows:
        pair = lambda a, b: f"{r[a]:,.0f} / {r[b]:,.0f}"
        lifecycle = lambda p: (f"{pair(f'merkle_lifecycle_{p}pct', f'naive_lifecycle_{p}pct')} "
                               f"({r[f'lifecycle_saving_{p}pct']:+.1f}%)")
        lines.append(f"| {r['n']} | {r['naive_batches']} | {pair('merkle_deploy_gas','naive_deploy_gas')} | "
                     f"{pair('merkle_publish_gas','naive_publish_gas')} | {r['publish_saving_pct']:+.1f}% | "
                     f"{pair('merkle_claim_mean','naive_claim_mean')} | {pair('merkle_claim_max','naive_claim_max')} | "
                     f"{lifecycle(25)} | {lifecycle(50)} | {lifecycle(100)} | {r['merkle_breakeven_claim_count']} |")
    lines += ["", "M = MerkleQFVault; S = NaiveStorageQFVault. Full receipt distributions (min, median, mean, max), per-N raw receipts and 25/50/100% totals are in the CSV and `phase3_gas_receipts.json`.",
              "", "Gas payer: the publisher pays deploy and publish transactions; the caller pays claim gas. The contract sends funds to the committed recipient even when a third party calls claim. The Merkle publisher also computes the tree off-chain. A single root uses O(1) storage per round, while successful claims populate up to O(N) `claimed` entries; each proof is O(log N).", ""]
    (GAS / "phase3_gas_benchmark.md").write_text("\n".join(lines), encoding="utf-8")

    FIGURES.mkdir(parents=True, exist_ok=True)
    nvals = [r["n"] for r in rows]
    fig, axes = plt.subplots(1, 2, figsize=(14, 5.2), constrained_layout=True)
    axes[0].plot(nvals, [r["merkle_publish_gas"] for r in rows], "o-", label="Merkle publish")
    axes[0].plot(nvals, [r["naive_publish_gas"] for r in rows], "s-", label="Naive publish (100/batch)")
    axes[0].set(title="A. Admin publish gas", xlabel="Number of grants N", ylabel="Gas used")
    axes[0].legend(); axes[0].grid(alpha=.25)
    colors = {25: "#2474a8", 50: "#d17219", 100: "#2e8b57"}
    for p in (25, 50, 100):
        axes[1].plot(nvals, [r[f"merkle_lifecycle_{p}pct"] for r in rows], "o-", color=colors[p], label=f"Merkle {p}%")
        axes[1].plot(nvals, [r[f"naive_lifecycle_{p}pct"] for r in rows], "s--", color=colors[p], label=f"Naive {p}%")
    axes[1].set(title="B. Publish + executed claims (deploy excluded)", xlabel="Number of grants N", ylabel="Gas used")
    axes[1].grid(alpha=.25); axes[1].legend(ncol=2, fontsize=8)
    fig.text(.5, -.01, "Per-claim mean gas and full receipt distributions: phase3_gas_benchmark.csv", ha="center", fontsize=9)
    fig.savefig(FIGURES / "fig04_gas_benchmark.png", dpi=300, bbox_inches="tight")
    plt.close(fig)
    print("Wrote phase3 gas CSV, Markdown, metadata, and 300 DPI fig04")


if __name__ == "__main__":
    main()
