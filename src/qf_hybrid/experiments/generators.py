"""Paired counterfactual donation worlds with exact per-project budget conservation."""
from collections import defaultdict
from dataclasses import dataclass
from decimal import Decimal, ROUND_HALF_UP
import numpy as np

CENT = Decimal("0.01")


@dataclass(frozen=True)
class Trial:
    family: str
    seed: int
    background: dict
    single: dict
    attack: dict
    targets: frozenset[str]
    attacker_single: dict
    attacker_attack: dict
    synthetic: bool


def _money(value):
    return Decimal(str(value)).quantize(CENT, rounding=ROUND_HALF_UP)


def _cents_split(value, n):
    cents = int((value / CENT).to_integral_value())
    q, r = divmod(cents, n)
    return [(q + (i < r)) * CENT for i in range(n)]


def synthetic_background(seed: int, heldout=False):
    rng = np.random.default_rng(seed)
    out = {}
    projects = [f"legit_{i:02d}" for i in range(24)]
    popularity = 1 / np.arange(1, 25, dtype=float)**1.1
    popularity /= popularity.sum()

    def add_diverse(prefix, n):
        for i in range(n):
            nproj = int(rng.integers(2, 6))
            picks = rng.choice(projects, size=nproj, replace=False, p=popularity)
            for p in picks:
                out[prefix+str(i), str(p)] = _money(np.clip(rng.lognormal(3.1, 0.7), 5, 100))

    add_diverse("diverse_", 165)
    if heldout:
        add_diverse("extra_diverse_", 25)
        for i in range(50):
            donor = f"strong_organic_{i}"
            out[donor, "legit_20"] = _money(rng.uniform(15, 25))
            if i >= 40:
                out[donor, "legit_21"] = _money(rng.uniform(15, 25))
    else:
        for i in range(35):
            donor = f"diverse_organic_{i}"
            core = rng.choice(["legit_12", "legit_13", "legit_14", "legit_15"], size=int(rng.integers(3, 5)), replace=False)
            outside = rng.choice(["legit_02", "legit_06", "legit_09"], size=int(rng.integers(1, 3)), replace=False)
            for p in list(core) + list(outside):
                out[donor, str(p)] = _money(rng.uniform(10, 60))
        for i in range(40):
            donor = f"concentrated_organic_{i}"
            out[donor, "legit_22"] = _money(rng.uniform(15, 25))
            if i >= 25:
                out[donor, "legit_23"] = _money(rng.uniform(15, 25))
    assert len({u for u, _ in out}) == 240
    assert len({p for _, p in out}) == 24
    return out


def _top_projects(background, n):
    totals = defaultdict(Decimal)
    for (_, p), amount in background.items():
        totals[p] += amount
    return [p for p, _ in sorted(totals.items(), key=lambda x: (-x[1], x[0]))[:n]]


def inject_attack(background, family: str, seed: int, *, synthetic: bool):
    """Return worlds with identical attacker total and per-project totals."""
    if any(u.startswith("attack_") or p.startswith("target_") for u, p in background):
        raise ValueError("Reserved attack namespace in background")
    single, attack = {}, {}
    targets = set()
    if synthetic:
        budget = Decimal("800") if family == "ring_4proj" else Decimal("600") if family == "ring_3proj" else Decimal("500")
    else:
        budget = max(Decimal("500"), _money(sum(background.values(), Decimal(0))*Decimal("0.02")))
    target = "target_0"
    if family.startswith("pure_split_m"):
        m = int(family.rsplit("m", 1)[1])
        targets.add(target)
        single["attack_single", target] = budget
        for i, amount in enumerate(_cents_split(budget, m)):
            attack[f"attack_split_{i}", target] = amount
    elif family in ("decoy_camouflage", "cross_cluster_split"):
        m = 40
        targets.add(target)
        share = Decimal("0.70") if family == "decoy_camouflage" else Decimal("0.75")
        target_money = _money(budget*share)
        decoys = _top_projects(background, 4 if family == "decoy_camouflage" else 8)
        decoy_amounts = _cents_split(budget-target_money, len(decoys))
        single["attack_single", target] = target_money
        for p, amount in zip(decoys, decoy_amounts):
            single["attack_single", p] = amount
        for i, amount in enumerate(_cents_split(target_money, m)):
            attack[f"attack_split_{i}", target] = amount
        if family == "decoy_camouflage":
            for j, (p, amount) in enumerate(zip(decoys, decoy_amounts)):
                for i, piece in enumerate(_cents_split(amount, m)):
                    if piece:
                        key = (f"attack_split_{i}", p)
                        attack[key] = attack.get(key, Decimal(0)) + piece
        else:
            for j, (p, amount) in enumerate(zip(decoys, decoy_amounts)):
                group = j//2
                for i, piece in enumerate(_cents_split(amount, 10)):
                    if piece:
                        attack[f"attack_split_{group*10+i}", p] = piece
    elif family in ("ring_3proj", "ring_4proj"):
        n = 3 if family == "ring_3proj" else 4
        targets = {f"target_{j}" for j in range(n)}
        if family == "ring_3proj":
            team_amounts = _cents_split(budget, n)
            # Integer cent matrix with exact column conservation, even for odd cents.
            matrix = [_cents_split(team_amounts[i], n) for i in range(n)]
            for i in range(n):
                matrix[i] = matrix[i][-i:] + matrix[i][:-i] if i else matrix[i]
            decoy = None
        else:
            rng = np.random.default_rng(seed)
            weights = rng.dirichlet(np.ones(n))
            base = [_money(Decimal("180")*Decimal(str(x))) for x in weights[:-1]]
            base.append(Decimal("180")-sum(base))
            matrix = [base[-i:] + base[:-i] if i else base[:] for i in range(n)]
            decoy = _top_projects(background, 1)[0]
        col_totals = [sum((matrix[i][j] for i in range(n)), Decimal(0)) for j in range(n)]
        for j, amount in enumerate(col_totals):
            single[f"attack_team_{j}", f"target_{j}"] = amount
        if decoy:
            for i in range(n):
                single[f"attack_team_{i}", decoy] = Decimal("20")
        for i in range(n):
            for j in range(n):
                for t, piece in enumerate(_cents_split(matrix[i][j], 10)):
                    if piece:
                        attack[f"attack_ring_{i}_{t}", f"target_{j}"] = piece
            if decoy:
                for t in range(10):
                    attack[f"attack_ring_{i}_{t}", decoy] = Decimal("2")
    else:
        raise ValueError(f"Unknown attack family: {family}")
    def by_project(events):
        totals = defaultdict(Decimal)
        for (_, p), amount in events.items():
            totals[p] += amount
        return dict(totals)
    if by_project(single) != by_project(attack) or sum(single.values(), Decimal(0)) != budget:
        raise AssertionError("Counterfactual budget or project totals differ")
    return Trial(family, seed, dict(background), dict(background)|single,
                 dict(background)|attack, frozenset(targets), single, attack, synthetic)
