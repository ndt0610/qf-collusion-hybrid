"""Profile four preselected rounds and benchmark exact G1/G2 candidate builders."""
import csv
import json
import os
import sys
import threading
import time
from pathlib import Path

import psutil

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/"src"))
from qf_hybrid.data.rounds import load_round
from qf_hybrid.graphs.core import build_graph, pair_work

ROUNDS = ("27", "29", "865", "867")


def measure(call):
    process = psutil.Process(os.getpid())
    initial = process.memory_info().rss
    peak = [initial]
    stop = threading.Event()
    def sample():
        while not stop.wait(0.01):
            peak[0] = max(peak[0], process.memory_info().rss)
    thread = threading.Thread(target=sample, daemon=True)
    thread.start()
    try:
        value = call()
        peak[0] = max(peak[0], process.memory_info().rss)
        return value, initial, peak[0]
    finally:
        stop.set()
        thread.join()


def main():
    config = json.loads((ROOT/"data/manifests/sources.json").read_text())
    hashes = {key: meta["sha256"] for key, meta in config["files"].items()}
    output = ROOT/"results/tables"
    output.mkdir(parents=True, exist_ok=True)
    rows = []
    for rid in ROUNDS:
        loaded = load_round(ROOT/"data/raw", "42161", rid, hashes)
        work = pair_work(loaded.contributions)
        for method in ("G1", "G2"):
            (graph, stats), rss_base, rss_peak = measure(lambda: build_graph(loaded.contributions, method, k=40, batch_size=128))
            item = {**loaded.audit, "graph_method": method, "pair_work": work,
                    "candidate_undirected": stats["candidate_undirected"],
                    "edges_k10": stats["edges_by_k_union"]["10"],
                    "edges_k20": stats["edges_by_k_union"]["20"],
                    "edges_k40": stats["edges_by_k_union"]["40"],
                    "seconds": round(stats["seconds"], 3),
                    "rss_baseline_mib": round(rss_base/(1024**2), 1),
                    "peak_rss_mib": round(rss_peak/(1024**2), 1),
                    "peak_delta_mib": round((rss_peak-rss_base)/(1024**2), 1)}
            rows.append(item)
            print(json.dumps(item, ensure_ascii=False), flush=True)
            del graph
    columns = sorted({key for row in rows for key in row})
    with (output/"phase1_data_graph_profile.csv").open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=columns)
        writer.writeheader()
        writer.writerows(rows)
    visible = ["round_id", "graph_method", "rows_total", "rows_kept", "raw_approved_join_ratio",
               "raw_rows_match_metadata", "raw_donors_match_metadata", "raw_usd_matches_metadata",
               "usd_nonpositive", "application_missing",
               "application_not_approved", "outside_window_or_invalid_time", "donors", "projects",
               "pair_work", "candidate_undirected", "edges_k10", "edges_k20", "edges_k40", "seconds", "peak_rss_mib"]
    lines = ["# Phase 1 data and graph profile", "", "Source: three SHA-256 locked Grants Data Portal files in `data/manifests/sources.json`. All rounds are Arbitrum chain 42161. Filters use current application APPROVED status, positive USD and recorded donation window.", "", "| " + " | ".join(visible) + " |", "|" + "|".join(["---"]*len(visible)) + "|"]
    for row in rows:
        lines.append("| " + " | ".join(str(row.get(key, 0)) for key in visible) + " |")
    lines += ["", "`pair_work` counts shared-project pairs with multiplicity, Σ_p d_p(d_p−1)/2. `candidate_undirected` counts unique pairs with at least one common project; both are computed after filtering. G1 and G2 process donors in batches of 128 without a dense N×N matrix. Each method computes candidate weights once at top-40; edge counts at k=10/20/40 derive from that same ranking. `seconds` is per graph build on this machine; `peak_rss_mib` samples whole-process resident memory every 10 ms and may miss shorter spikes. It includes Python and loaded data; see CSV for baseline and delta. No Louvain or mechanism runtime is included.", "", "Held-out recommendation: reserve 42161:865 and 42161:867 (GG23, 2025) if the table shows acceptable metadata; use 42161:27 for empirical dev and 42161:29 for same-season sensitivity only. Final GĐ 2 protocol should freeze this assignment before tuning.", ""]
    (output/"phase1_data_graph_profile.md").write_text("\n".join(lines), encoding="utf-8")


if __name__ == "__main__":
    main()
