"""Evaluate exactly the frozen nine mechanisms; never fit on held-out data."""
import hashlib
import json
import math
import sys
from pathlib import Path
from time import perf_counter

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/"src"))
from qf_hybrid.data.rounds import load_round
from qf_hybrid.experiments.generators import inject_attack, synthetic_background
from qf_hybrid.experiments.metrics import (attack_gain, damage, diff_vs_standard,
    spillover, suppression, unallocated)
from qf_hybrid.experiments.reporting import write_table
from qf_hybrid.experiments.stats import holm, paired_inference
from qf_hybrid.experiments.trials import WorldCache
from qf_hybrid.mechanisms.core import BRANCHES

METHODS = ("standard_qf", "pairwise_qf", "coqf_paper2025_alg2", "hard_cluster", *BRANCHES)
SYNTH_FAMILIES = ("decoy_camouflage", "cross_cluster_split", "ring_4proj")
EMPIRICAL_FAMILIES = ("pure_split_m40", "decoy_camouflage", "cross_cluster_split")
COMPARISONS = {
    "ablation": (("soft_full", "soft_base"), ("soft_shapley", "soft_base"),
                 ("soft_centrality", "soft_base"), ("soft_full", "size_only")),
    "baseline": (("soft_full", "standard_qf"), ("soft_full", "pairwise_qf"),
                 ("soft_full", "coqf_paper2025_alg2"), ("soft_full", "hard_cluster")),
}


def _read_frozen():
    path = ROOT/"configs/heldout/frozen_mechanisms.json"
    frozen = json.loads(path.read_text(encoding="utf-8"))
    if frozen["protocol_sha256"] != hashlib.sha256((ROOT/"docs/EXPERIMENT_PROTOCOL.md").read_bytes()).hexdigest():
        raise ValueError("Protocol changed after dev freeze")
    if frozen["source_manifest_sha256"] != hashlib.sha256((ROOT/"data/manifests/sources.json").read_bytes()).hexdigest():
        raise ValueError("Data manifest changed after dev freeze")
    if frozen["split"] != {"dev": "42161:27", "heldout": ["42161:865", "42161:867"], "sensitivity": "42161:29"}:
        raise ValueError("Unexpected frozen data split")
    return frozen


def _allocations(contributions, selected, pool):
    started = perf_counter()
    keys = {tuple(selected[name]["graph_key"]) for name in BRANCHES}
    hard_key = tuple(selected["soft_full"]["graph_key"])
    world = WorldCache(contributions, sorted(keys), seed=42)
    result = {}
    for name in METHODS:
        if name in BRANCHES:
            entry = selected[name]
            result[name] = world.soft(tuple(entry["graph_key"]), name, [entry["beta"]], pool)[0]
        elif name == "pairwise_qf":
            result[name] = world.baseline(name, pool, tau=selected[name]["beta"]["tau"])
        elif name == "hard_cluster":
            result[name] = world.baseline(name, pool, hard_key=hard_key)
        else:
            result[name] = world.baseline(name, pool)
    return world.projects, result, {"graph_seconds": world.graph_seconds, "wall_seconds": perf_counter()-started}


def _base_metric_row(method, background_alloc, standard, projects, valid, pool, synthetic):
    row = {"mechanism": method, "pool_usd": pool}
    if synthetic:
        aggregate, p50, p90 = damage(standard, background_alloc, projects, valid)
        row.update(mech_damage_H=float(aggregate), mech_damage_p50_proj=float(p50),
                   mech_damage_p90_proj=float(p90), diff_vs_standard_background_abs_usd=math.nan,
                   diff_vs_standard_background_abs_pct=math.nan)
    else:
        difference, fraction = diff_vs_standard(standard, background_alloc, projects, set(), pool)
        row.update(mech_damage_H=math.nan, mech_damage_p50_proj=math.nan,
                   mech_damage_p90_proj=math.nan, diff_vs_standard_background_abs_usd=difference,
                   diff_vs_standard_background_abs_pct=fraction)
    return row


def _attack_rows(trial, base_rows, single, attack, projects, pool, round_id, seed, synthetic):
    std_signed = attack_gain(single["standard_qf"], attack["standard_qf"], projects, trial.targets, pool)[0]
    rows = []
    for method in METHODS:
        signed, positive, signed_pct, positive_pct = attack_gain(single[method], attack[method], projects, trial.targets, pool)
        spill_abs, spill_loss, spill_abs_pct, spill_loss_pct = spillover(single[method], attack[method], projects, trial.targets, pool)
        row = {**base_rows[method], "dataset": "synthetic" if synthetic else "empirical",
               "round_id": round_id, "family": trial.family, "seed": seed,
               "design_seed": trial.seed, "targets": ",".join(sorted(trial.targets)),
               "delta_A_signed_usd": float(signed), "delta_A_pos_usd": float(positive),
               "delta_A_signed_pct": float(signed_pct), "delta_A_pos_pct": float(positive_pct),
               "suppression_vs_std": suppression(float(signed), float(std_signed), pool),
               "spillover_background_abs_usd": float(spill_abs),
               "spillover_background_loss_usd": float(spill_loss),
               "spillover_background_abs_pct": float(spill_abs_pct),
               "spillover_background_loss_pct": float(spill_loss_pct),
               "unallocated_single_usd": unallocated(single[method], pool),
               "unallocated_attack_usd": unallocated(attack[method], pool),
               "unallocated_pct": unallocated(attack[method], pool)/pool,
               "empirical_design_repeated": not synthetic}
        rows.append(row)
    return rows


def _paired_stats(synthetic_rows):
    by_trial = {(row["seed"], row["family"], row["mechanism"]): row
                for row in synthetic_rows if row["family"] in SYNTH_FAMILIES}
    output = []
    for family_name, pairs in COMPARISONS.items():
        group = []
        for first, second in pairs:
            # Three families share each seed's background; infer on ten independent seed blocks.
            per_seed = []
            for seed in range(100, 110):
                differences = [by_trial[seed, family, first]["delta_A_pos_pct"]-
                               by_trial[seed, family, second]["delta_A_pos_pct"]
                               for family in SYNTH_FAMILIES]
                per_seed.append(float(np.mean(differences)))
            row = {"comparison_family": family_name, "first": first, "second": second,
                   "metric": "delta_A_pos_pct", "n_trial_pairs": 30, "n_seed_blocks": 10,
                   **paired_inference(per_seed, seed=9182)}
            group.append(row)
        output.extend(holm(group))
    return output


def main():
    started = perf_counter()
    frozen = _read_frozen()
    selected = frozen["selected"]["0.05"]
    synthetic_rows, empirical_rows, runtime = [], [], []
    for seed in range(100, 110):
        background = synthetic_background(seed, heldout=True)
        projects, bg, timing = _allocations(background, selected, 10_000)
        valid = {p for _, p in background}
        base = {method: _base_metric_row(method, bg[method], bg["standard_qf"], projects,
                                          valid, 10_000, True) for method in METHODS}
        for method in METHODS:
            synthetic_rows.append({**base[method], "dataset": "synthetic", "round_id": "synthetic_heldout",
                                   "family": "strongly_concentrated_organic", "seed": seed, "design_seed": seed,
                                   "targets": "", "delta_A_signed_usd": math.nan, "delta_A_pos_usd": math.nan,
                                   "delta_A_signed_pct": math.nan, "delta_A_pos_pct": math.nan,
                                   "suppression_vs_std": math.nan, "spillover_background_abs_usd": math.nan,
                                   "spillover_background_loss_usd": math.nan, "spillover_background_abs_pct": math.nan,
                                   "spillover_background_loss_pct": math.nan,
                                   "unallocated_single_usd": unallocated(bg[method], 10_000),
                                   "unallocated_attack_usd": math.nan,
                                   "unallocated_pct": unallocated(bg[method], 10_000)/10_000,
                                   "empirical_design_repeated": False})
        runtime.append({"dataset": "synthetic", "seed": seed, "family": "attack_free", **timing})
        print(f"heldout synthetic organic seed {seed}: {timing['wall_seconds']:.1f}s", flush=True)
        for family in SYNTH_FAMILIES:
            trial = inject_attack(background, family, seed, synthetic=True)
            projects, single, t1 = _allocations(trial.single, selected, 10_000)
            _, attack, t2 = _allocations(trial.attack, selected, 10_000)
            synthetic_rows.extend(_attack_rows(trial, base, single, attack, projects, 10_000,
                                               "synthetic_heldout", seed, True))
            runtime.append({"dataset": "synthetic", "seed": seed, "family": family,
                            "graph_seconds": t1["graph_seconds"]+t2["graph_seconds"],
                            "wall_seconds": t1["wall_seconds"]+t2["wall_seconds"]})
            print(f"heldout synthetic {family} seed {seed}: {t1['wall_seconds']+t2['wall_seconds']:.1f}s", flush=True)
    source = json.loads((ROOT/"data/manifests/sources.json").read_text())
    hashes = {name: info["sha256"] for name, info in source["files"].items()}
    for rid in ("865", "867", "29"):
        background = load_round(ROOT/"data/raw", "42161", rid, hashes).contributions
        projects, bg, timing = _allocations(background, selected, 100_000)
        base = {method: _base_metric_row(method, bg[method], bg["standard_qf"], projects,
                                          set(), 100_000, False) for method in METHODS}
        runtime.append({"dataset": "empirical", "round_id": rid, "family": "attack_free", **timing})
        print(f"heldout empirical {rid} background: {timing['wall_seconds']:.1f}s", flush=True)
        for family in EMPIRICAL_FAMILIES:
            trial = inject_attack(background, family, 2000, synthetic=False)
            projects, single, t1 = _allocations(trial.single, selected, 100_000)
            _, attack, t2 = _allocations(trial.attack, selected, 100_000)
            for seed in range(2000, 2005):
                empirical_rows.extend(_attack_rows(trial, base, single, attack, projects, 100_000, rid, seed, False))
            runtime.append({"dataset": "empirical", "round_id": rid, "family": family,
                            "seed_labels": 5, "unique_world_pairs": 1,
                            "graph_seconds": t1["graph_seconds"]+t2["graph_seconds"],
                            "wall_seconds": t1["wall_seconds"]+t2["wall_seconds"]})
            print(f"heldout empirical {rid} {family}: {t1['wall_seconds']+t2['wall_seconds']:.1f}s", flush=True)
    stats = _paired_stats(synthetic_rows)
    tables = ROOT/"results/tables"
    write_table(tables/"phase2_heldout_synthetic", synthetic_rows,
                "Phase 2 held-out synthetic trials", "Known-valid H; 10 independent seeds per family. Organic rows are attack-free. Values marked pct are fractions of B. Positive target gain is not attacker net profit.")
    write_table(tables/"phase2_heldout_empirical", empirical_rows,
                "Phase 2 held-out empirical injections", "Background projects have unknown integrity. Five seed labels per family share one deterministic injected design and are descriptive repeats, not independent trials. Round 29 is same-season sensitivity, not temporal held-out.")
    write_table(tables/"phase2_paired_ablation_stats", stats,
                "Phase 2 paired comparisons", "First minus second on positive target gain/B; negative favors first. n_trial_pairs=30, n_seed_blocks=10; bootstrap and sign flips use seed-block means to respect shared backgrounds. Holm is applied separately to each comparison family.")
    (tables/"phase2_heldout_runtime.json").write_text(json.dumps(runtime, indent=2)+"\n", encoding="utf-8")
    print(f"Held-out complete: {perf_counter()-started:.1f}s; {len(synthetic_rows)} synthetic and {len(empirical_rows)} empirical rows", flush=True)


if __name__ == "__main__":
    main()
