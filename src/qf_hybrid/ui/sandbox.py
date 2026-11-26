"""Presentation sandbox: fresh paired worlds, with no writes to frozen results."""
from __future__ import annotations

import json
from decimal import Decimal
from pathlib import Path
from time import perf_counter

import numpy as np

from qf_hybrid.experiments.generators import Trial, inject_attack, synthetic_background
from qf_hybrid.experiments.metrics import attack_gain, damage
from qf_hybrid.experiments.trials import WorldCache

ROOT = Path(__file__).resolve().parents[3]
POOL = 10_000
LABELS = {
    "standard_qf": "Standard QF", "pairwise_qf": "Pairwise QF",
    "coqf_paper2025_alg2": "CO-QF (2025 Alg. 2)", "hard_cluster": "HardCluster",
    "soft_base": "Soft Base", "soft_shapley": "Soft + Shapley",
    "soft_full": "Soft Full", "soft_centrality": "Soft + Centrality",
    "size_only": "Chỉ kích thước cụm",
}
FAMILIES = {
    "pure_split": "Chia ví thuần", "decoy_camouflage": "Ngụy trang với dự án decoy",
    "cross_cluster_split": "Tách qua nhiều cụm", "ring_3proj": "Vòng ba dự án",
}


def family_label(family: str) -> str:
    if family in FAMILIES:
        return FAMILIES[family]
    if family == "ring_4proj":
        return "Vòng bốn dự án"
    if family.startswith("pure_split_m"):
        return f"Chia ví thuần · {family.rsplit('m', 1)[-1]} ví"
    return family.replace("_", " ")


def frozen_config() -> dict:
    return json.loads((ROOT / "configs/heldout/frozen_mechanisms.json").read_text(encoding="utf-8"))["selected"]["0.05"]


def _split_weighted(total_cents: int, weights: list[int]) -> list[int]:
    denom = sum(weights)
    if denom == 0:
        return [0] * len(weights)
    base = [total_cents * w // denom for w in weights]
    residue = total_cents - sum(base)
    order = sorted(range(len(weights)), key=lambda i: (-(total_cents * weights[i] % denom), i))
    for i in order[:residue]:
        base[i] += 1
    return base


def _cents(amount: Decimal) -> int:
    return int(amount * 100)


def make_trial(family: str, budget: int, m: int, seed: int,
               background_override: dict | None = None) -> Trial:
    """Scale an existing research generator template, retaining exact project totals."""
    if family not in FAMILIES or budget < 50 or m < 1:
        raise ValueError("Invalid sandbox parameters")
    background = (synthetic_background(seed, heldout=True) if background_override is None
                  else dict(background_override))
    template_family = f"pure_split_m{max(1, m)}" if family == "pure_split" else family
    source = inject_attack(background, template_family, seed, synthetic=True)
    projects = sorted({project for _, project in source.attacker_single})
    old_totals = [sum((_cents(amount) for (_, p), amount in source.attacker_single.items() if p == project))
                  for project in projects]
    new_totals = _split_weighted(budget * 100, old_totals)
    single: dict = {}
    attack: dict = {}
    for project, total in zip(projects, new_totals):
        donors = sorted(donor for donor, p in source.attacker_single if p == project)
        weights = [_cents(source.attacker_single[donor, project]) for donor in donors]
        for donor, cents in zip(donors, _split_weighted(total, weights)):
            if cents:
                single[donor, project] = Decimal(cents) / 100
        attack_donors = sorted(donor for donor, p in source.attacker_attack if p == project)
        original_weights = [_cents(source.attacker_attack[donor, project]) for donor in attack_donors]
        if family == "cross_cluster_split" and project not in source.targets:
            decoys = sorted(p for p in projects if p not in source.targets)
            group = decoys.index(project) // 2
            indices = [i for i in range(m) if min(3, i * 4 // m) == group]
            if not indices:
                indices = [min(m-1, group*m//4)]
        else:
            indices = list(range(m))
        new_donors = [f"attack_split_{i}" for i in indices]
        weights = [original_weights[min(len(original_weights)-1, j*len(original_weights)//len(indices))]
                   for j in range(len(indices))]
        for donor, cents in zip(new_donors, _split_weighted(total, weights)):
            if cents:
                attack[donor, project] = Decimal(cents) / 100
    assert sum(single.values()) == sum(attack.values()) == Decimal(budget)
    assert {p: sum(v for (_, q), v in single.items() if p == q) for p in projects} == {
        p: sum(v for (_, q), v in attack.items() if p == q) for p in projects}
    return Trial(family, seed, background, background | single, background | attack,
                 source.targets, single, attack, True)


def _allocation(world: WorldCache, mechanism: str, selected: dict, pool: int) -> np.ndarray:
    if mechanism in ("standard_qf", "pairwise_qf", "coqf_paper2025_alg2", "hard_cluster"):
        return world.baseline(mechanism, pool, tau=selected["pairwise_qf"]["beta"]["tau"],
                              hard_key=tuple(selected["soft_full"]["graph_key"]))
    spec = selected[mechanism]
    return world.soft(tuple(spec["graph_key"]), mechanism, [spec["beta"]], pool)[0]


def background_with_organic_wallets(seed: int, count: int) -> dict:
    """Keep the held-out generator fixed except for the labeled concentrated cohort."""
    if not 0 <= count <= 100:
        raise ValueError("Concentrated honest-wallet count must be 0..100")
    background = synthetic_background(seed, heldout=True)
    if count < 50:
        return {key: amount for key, amount in background.items()
                if not (key[0].startswith("strong_organic_") and
                        int(key[0].rsplit("_", 1)[-1]) >= count)}
    rng = np.random.default_rng(seed + 1_000_003)
    for i in range(50, count):
        donor = f"strong_organic_{i}"
        background[donor, "legit_20"] = Decimal(str(float(rng.uniform(15, 25)))).quantize(Decimal("0.01"))
        if i >= 40:
            background[donor, "legit_21"] = Decimal(str(float(rng.uniform(15, 25)))).quantize(Decimal("0.01"))
    return background


def run_sandbox(family: str = "decoy_camouflage", budget: int = 500, m: int = 40,
                seed: int = 100, *, pool: int = POOL, organic_wallets: int = 50,
                custom_beta: dict | None = None, custom_graph_key: tuple = ("G2", 40, 0.5),
                custom_tau: int = 500) -> dict:
    started = perf_counter()
    if pool <= 0 or custom_tau <= 0:
        raise ValueError("Pool and Pairwise tau must be positive")
    trial = make_trial(family, budget, m, seed,
                       background_with_organic_wallets(seed, organic_wallets))
    selected = frozen_config()
    mechanisms = ("standard_qf", "pairwise_qf", "coqf_paper2025_alg2", "hard_cluster",
                  "soft_base", "soft_shapley", "soft_full")
    keys = tuple(sorted({tuple(spec["graph_key"]) for spec in selected.values() if spec["graph_key"]}
                        | {tuple(custom_graph_key)}))
    worlds = {name: WorldCache(events, keys=keys, seed=42) for name, events in
              (("background", trial.background), ("single", trial.single), ("attack", trial.attack))}
    valid = set(worlds["background"].projects)
    base_standard = _allocation(worlds["background"], "standard_qf", selected, pool)
    rows = []
    allocations = {}
    default_beta = selected["soft_base"]["beta"]
    custom_beta = dict(default_beta if custom_beta is None else custom_beta)
    display = list(mechanisms) + ["custom_soft"]
    if custom_tau != selected["pairwise_qf"]["beta"]["tau"]:
        display.append("pairwise_custom")
    for mechanism in display:
        if mechanism == "custom_soft":
            calc = lambda world: world.soft(tuple(custom_graph_key), "soft_full", [custom_beta], pool)[0]
            label = "Tùy chỉnh của tôi"
        elif mechanism == "pairwise_custom":
            calc = lambda world: world.baseline("pairwise_qf", pool, tau=custom_tau)
            label = f"Pairwise QF · τ={custom_tau}"
        else:
            calc = lambda world: _allocation(world, mechanism, selected, pool)
            label = LABELS[mechanism]
        bg = calc(worlds["background"])
        single = calc(worlds["single"])
        attack = calc(worlds["attack"])
        loss = float(damage(base_standard, bg, worlds["background"].projects, valid)[0])
        gain = float(attack_gain(single, attack, worlds["attack"].projects,
                                 trial.targets, pool)[3])
        rows.append({"mechanism": mechanism, "label": label,
                     "gain_pct": gain * 100, "damage_pct": loss * 100,
                     "policy_ok": loss <= 0.05})
        allocations[mechanism] = dict(zip(worlds["attack"].projects, map(float, attack)))
    return {"rows": rows, "seconds": perf_counter()-started, "trial": trial,
            "allocations": allocations, "pool": pool, "organic_wallets": organic_wallets,
            "family": family, "budget": budget, "m": m, "seed": seed}


def cluster_snapshot(with_attack: bool, overview: bool = False) -> dict:
    """Return one partition's descriptive features for a two-stage visual."""
    background = synthetic_background(100, heldout=True)
    events = inject_attack(background, "decoy_camouflage", 100, synthetic=True).attack if with_attack else background
    from qf_hybrid.graphs.core import graph_family, louvain
    from qf_hybrid.features.core import extract
    graph = graph_family(events, "G2")[0][40 if overview else 10]
    communities = louvain(graph, resolution=0.5 if overview else 1.5, seed=42)
    features = extract(events, graph, communities)
    selected = frozen_config()
    def lam(f, branch):
        beta = selected[branch]["beta"]
        value = (beta["beta0"] + beta["coh"]*f.cohesion + beta["conc"]*f.proj_conc +
                 beta["shapley"]*f.shapley_share + beta["centrality"]*f.centrality)
        return max(0., min(1., value)) if len(f.donors) > 1 else 0.
    rows = []
    for i, f in enumerate(features):
        attackers = sum(d.startswith("attack_") for d in f.donors)
        rows.append({"id": i+1, "size": len(f.donors), "attackers": attackers,
                     "cohesion": f.cohesion, "shapley": f.shapley_share,
                     "lambda_base": lam(f, "soft_base"), "lambda_full": lam(f, "soft_full"),
                     "members": sorted(f.donors), "concentration": f.proj_conc})
    return {"rows": rows, "graph": graph, "events": events}
