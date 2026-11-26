"""Measure sparse pairwise Gram construction and all five tau evaluations."""
import json
import sys
from pathlib import Path
from time import perf_counter

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/"src"))
from qf_hybrid.data.rounds import load_round
from qf_hybrid.experiments.reporting import write_table
from qf_hybrid.mechanisms.core import PairwiseSparseCache


def main():
    source = json.loads((ROOT/"data/manifests/sources.json").read_text())
    hashes = {name: info["sha256"] for name, info in source["files"].items()}
    rows = []
    for rid in ("27", "865", "867"):
        c = load_round(ROOT/"data/raw", "42161", rid, hashes).contributions
        start = perf_counter()
        cache = PairwiseSparseCache(c)
        build = perf_counter()-start
        start = perf_counter()
        for tau in (1, 5, 25, 100, 500):
            scores = cache.score(tau)
            if any(x < 0 for x in scores.values()):
                raise AssertionError("Negative pairwise score")
        score = perf_counter()-start
        rows.append({"round_id": rid, "donors": len(cache.donors), "projects": len(cache.projects),
                     "nonzero_directed_pairs": cache.t.nnz, "build_seconds": build,
                     "five_tau_seconds": score, "total_seconds": build+score})
        print(rows[-1], flush=True)
    write_table(ROOT/"results/tables/phase2_pairwise_sparse_benchmark", rows,
                "Sparse pairwise benchmark", "Real wall-clock measurements on this machine. Sparse Gram matrix has no dense N×N allocation. Timings include cache construction and all five predeclared tau values, but exclude parquet loading and filtering.")


if __name__ == "__main__":
    main()
