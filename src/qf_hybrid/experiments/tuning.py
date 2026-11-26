"""Stream all predeclared dev candidates; freeze before held-out access."""
from collections import defaultdict
from itertools import product
import gc
import json
from pathlib import Path
from time import perf_counter

import numpy as np

from qf_hybrid.data.rounds import load_round
from qf_hybrid.experiments.generators import inject_attack, synthetic_background
from qf_hybrid.experiments.metrics import attack_gain, damage
from qf_hybrid.experiments.trials import GRAPH_KEYS, WorldCache
from qf_hybrid.mechanisms.core import BETA_GRID, BRANCHES

TAUS = (1, 5, 25, 100, 500)
DEV_FAMILIES = ("pure_split_m20", "pure_split_m50", "ring_3proj", "empirical_pure_split_m40", "empirical_ring_3proj")
DELTAS = (0.02, 0.05, 0.10)


def pareto_rows(flat_rows):
    """Global nondominated safety/fairness points, minimizing both columns."""
    ranked = sorted(flat_rows, key=lambda row: (float(row["dev_mech_damage"]),
                                                float(row["dev_attack_gain"]), row["mechanism"]))
    frontier = []
    best_gain = float("inf")
    for row in ranked:
        gain = float(row["dev_attack_gain"])
        if gain < best_gain-1e-12:
            frontier.append(row)
            best_gain = gain
    return frontier


def beta_grid(branch):
    if branch == "size_only":
        return [dict(beta0=b0, coh=0.0, conc=0.0, shapley=0.0, centrality=0.0, size=size)
                for b0, size in product(BETA_GRID["beta0"], BETA_GRID["size"])]
    entries = []
    s_grid = BETA_GRID["shapley"] if branch in ("soft_shapley", "soft_full") else (0.0,)
    c_grid = BETA_GRID["centrality"] if branch in ("soft_centrality", "soft_full") else (0.0,)
    for b0, coh, conc, s, c in product(BETA_GRID["beta0"], BETA_GRID["coh"], BETA_GRID["conc"], s_grid, c_grid):
        entries.append(dict(beta0=b0, coh=coh, conc=conc, shapley=s, centrality=c, size=0.0))
    return entries


def specs():
    return {("soft", key, branch): beta_grid(branch) for key in GRAPH_KEYS for branch in BRANCHES} | {
        ("pairwise", None, "pairwise_qf"): [{"tau": tau} for tau in TAUS]} | {
        ("baseline", None, name): [{}] for name in ("standard_qf", "coqf_paper2025_alg2")} | {
        ("hard", key, "hard_cluster"): [{}] for key in GRAPH_KEYS}


def world_allocations(contributions, candidates, pool):
    started = perf_counter()
    world = WorldCache(contributions)
    allocations = {}
    for spec, options in candidates.items():
        kind, key, branch = spec
        if kind == "soft":
            allocations[spec] = world.soft(key, branch, options, pool)
        elif kind == "pairwise":
            allocations[spec] = np.array([world.baseline("pairwise_qf", pool, tau=x["tau"]) for x in options])
        elif kind == "hard":
            allocations[spec] = world.baseline("hard_cluster", pool, hard_key=key)[None, :]
        else:
            allocations[spec] = world.baseline(branch, pool)[None, :]
    result = (world.projects, allocations, world.graph_seconds, perf_counter()-started)
    del world
    gc.collect()
    return result


def _accumulate_damage(storage, candidates, background, pool, projects, allocs):
    valid = {p for _, p in background}
    standard = allocs[("baseline", None, "standard_qf")][0]
    for spec in candidates:
        aggregate, _, _ = damage(standard, allocs[spec], projects, valid)
        storage[spec] += aggregate


def _accumulate_gain(storage, candidates, family, targets, pool, projects, single, attack):
    for spec in candidates:
        _, _, _, positive_pct = attack_gain(single[spec], attack[spec], projects, targets, pool)
        storage[spec][family] += positive_pct


def _selection_rank(row):
    beta = row["beta"]
    key = row["graph_key"]
    return (row["dev_attack_gain"], row["dev_mech_damage"],
            sum(abs(float(v)) for v in beta.values() if isinstance(v, (int, float))),
            0 if key is None or key[0] == "G1" else 1,
            0 if key is None else key[1], 0 if key is None else abs(key[2]-1),
            json.dumps(beta, sort_keys=True))


def select(rows, branch, delta):
    options = [row for row in rows if row["mechanism"] == branch]
    feasible = [row for row in options if row["dev_mech_damage"] <= delta+1e-15]
    if feasible:
        chosen = min(feasible, key=_selection_rank)
        return {**chosen, "delta_max": delta, "infeasible_at_delta": False}
    chosen = min(options, key=lambda row: (row["dev_mech_damage"], *_selection_rank(row)))
    return {**chosen, "delta_max": delta, "infeasible_at_delta": True}


def run_dev(root: Path, progress=print):
    started = perf_counter()
    candidates = specs()
    damage_sum = {key: np.zeros(len(value)) for key, value in candidates.items()}
    gain_sum = {key: {family: np.zeros(len(value)) for family in DEV_FAMILIES} for key, value in candidates.items()}
    counts = defaultdict(int)
    runtime = []
    for seed in range(6):
        background = synthetic_background(seed)
        projects, allocations, graph_seconds, elapsed = world_allocations(background, candidates, 10_000)
        _accumulate_damage(damage_sum, candidates, background, 10_000, projects, allocations)
        runtime.append(dict(stage="synthetic_attack_free", seed=seed, graph_seconds=graph_seconds, seconds=elapsed))
        progress(f"dev attack-free seed {seed}: {elapsed:.1f}s", flush=True)
        del allocations
        for family in DEV_FAMILIES[:3]:
            trial = inject_attack(background, family, seed, synthetic=True)
            projects, single, gs, ts = world_allocations(trial.single, candidates, 10_000)
            _, attack, ga, ta = world_allocations(trial.attack, candidates, 10_000)
            _accumulate_gain(gain_sum, candidates, family, trial.targets, 10_000, projects, single, attack)
            counts[family] += 1
            runtime.append(dict(stage=family, seed=seed, graph_seconds=gs+ga, seconds=ts+ta))
            progress(f"dev {family} seed {seed}: {ts+ta:.1f}s", flush=True)
            del single, attack
    source = json.loads((root/"data/manifests/sources.json").read_text())
    hashes = {name: info["sha256"] for name, info in source["files"].items()}
    empirical = load_round(root/"data/raw", "42161", "27", hashes).contributions
    for family in ("pure_split_m40", "ring_3proj"):
        # All five requested empirical seeds generate the same deterministic design.
        # Evaluate once and retain the five-design count without treating it as evidence of replication.
        trial = inject_attack(empirical, family, 1000, synthetic=False)
        projects, single, gs, ts = world_allocations(trial.single, candidates, 100_000)
        _, attack, ga, ta = world_allocations(trial.attack, candidates, 100_000)
        label = "empirical_"+family
        _accumulate_gain(gain_sum, candidates, label, trial.targets, 100_000, projects, single, attack)
        counts[label] += 1
        runtime.append(dict(stage=label, design_seeds=5, unique_world_pairs=1, graph_seconds=gs+ga, seconds=ts+ta))
        progress(f"dev {label}: {ts+ta:.1f}s (five identical seed designs)", flush=True)
        del single, attack
    rows = []
    for spec, options in candidates.items():
        kind, key, mechanism = spec
        for i, beta in enumerate(options):
            family_means = {family: float(gain_sum[spec][family][i]/counts[family]) for family in DEV_FAMILIES}
            rows.append(dict(mechanism=mechanism, graph_key=key, beta=beta,
                             dev_mech_damage=float(damage_sum[spec][i]/6),
                             dev_attack_gain=float(np.mean(list(family_means.values()))),
                             family_means=family_means))
    selected = [select(rows, branch, delta) for delta in DELTAS
                for branch in ("pairwise_qf", *BRANCHES)]
    frozen = {"schema_version": 1, "phase": 2, "split": {"dev": "42161:27", "heldout": ["42161:865", "42161:867"], "sensitivity": "42161:29"},
              "pool_synthetic": 10000, "pool_empirical": 100000, "louvain_seed": 42,
              "selected": {str(delta): {row["mechanism"]: {"graph_key": row["graph_key"], "beta": row["beta"],
                    "dev_mech_damage": row["dev_mech_damage"], "dev_attack_gain": row["dev_attack_gain"],
                    "infeasible_at_delta": row["infeasible_at_delta"]} for row in selected if row["delta_max"] == delta} for delta in DELTAS},
              "hard_cluster_graph_source": "soft_full at delta=0.05",
              "empirical_seed_replicates": "deterministic identical design; one unique world pair per family",
              "dev_wall_seconds": perf_counter()-started}
    return rows, selected, frozen, runtime
