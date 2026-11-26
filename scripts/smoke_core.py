"""Phase 1 real-data integration smoke; no red-team simulation or tuning."""
import json
import sys
from pathlib import Path
from time import perf_counter

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/"src"))

from qf_hybrid.data.rounds import load_round
from qf_hybrid.graphs.core import build_graph, louvain
from qf_hybrid.features.core import extract
from qf_hybrid.mechanisms.core import (BRANCHES, coqf_paper2025_alg2, hard_cluster,
    lambdas_for_branch, pairwise_qf, soft_discounting, standard_qf)
from qf_hybrid.allocation.core import normalize


def main():
    manifest = json.loads((ROOT/"data/manifests/sources.json").read_text())
    hashes = {name: info["sha256"] for name, info in manifest["files"].items()}
    data = load_round(ROOT/"data/raw", "42161", "27", hashes)
    graph, graph_stats = build_graph(data.contributions, "G1", k=10)
    communities = louvain(graph, resolution=1.0, seed=42)
    features = extract(data.contributions, graph, communities)
    checks = {}
    beta = {"beta0": 0.0, "coh": 0.4, "conc": 0.4, "shapley": 0.4,
            "centrality": 0.3, "size": 0.5}
    methods = {
        "standard_qf": lambda: standard_qf(data.contributions),
        "pairwise_qf": lambda: pairwise_qf(data.contributions, 25),
        "coqf_paper2025_alg2": lambda: coqf_paper2025_alg2(data.contributions),
        "hard_cluster": lambda: hard_cluster(data.contributions, communities),
    }
    for branch in BRANCHES:
        methods[branch] = lambda branch=branch: soft_discounting(
            data.contributions, communities,
            lambdas_for_branch(features, branch, beta, len(graph)))
    for name, call in methods.items():
        started = perf_counter()
        scores = call()
        allocations, unallocated = normalize(scores, 100000)
        if len(scores) != data.audit["projects"] or any(value < 0 for value in scores.values()):
            raise AssertionError(f"Invalid scores in {name}")
        if abs(sum(allocations.values())+unallocated-100000) > 1e-20:
            raise AssertionError(f"Budget mismatch in {name}")
        checks[name] = {"projects": len(scores), "raw_score_total": round(sum(scores.values()), 6),
                        "seconds": round(perf_counter()-started, 3)}
        print(name, checks[name], flush=True)
    report = {"round": "42161:27", "graph": {key: graph_stats[key] for key in ("method","k","donors","edges_after_topk_union")},
              "clusters": len(communities), "methods": checks,
              "scope": "one configuration, no tuning, no attacker injection; integration feasibility only"}
    target = ROOT/"results/tables/phase1_core_smoke.json"
    target.write_text(json.dumps(report, indent=2)+"\n", encoding="utf-8")
    print(f"saved {target}")


if __name__ == "__main__":
    main()
