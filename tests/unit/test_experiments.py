from collections import defaultdict
from decimal import Decimal
from math import isnan

import numpy as np
import pytest

from qf_hybrid.allocation.core import normalize
from qf_hybrid.experiments.generators import inject_attack, synthetic_background
from qf_hybrid.experiments.metrics import suppression, unallocated
from qf_hybrid.experiments.stats import holm, paired_inference
from qf_hybrid.experiments.trials import WorldCache
from qf_hybrid.graphs.core import build_graph, graph_family
from qf_hybrid.mechanisms.core import (PairwiseSparseCache, coqf_default_fast,
    coqf_paper2025_alg2, lambdas_for_branch, pairwise_qf, soft_discounting)


@pytest.mark.parametrize("family", ["pure_split_m20", "pure_split_m50", "pure_split_m40",
    "ring_3proj", "ring_4proj", "decoy_camouflage", "cross_cluster_split"])
def test_counterfactual_budget_by_project(family):
    background = synthetic_background(100, heldout=True)
    trial = inject_attack(background, family, 100, synthetic=True)
    def by_project(events):
        out = defaultdict(Decimal)
        for (_, p), amount in events.items():
            out[p] += amount
        return dict(out)
    assert by_project(trial.attacker_single) == by_project(trial.attacker_attack)
    assert sum(trial.attacker_single.values()) == sum(trial.attacker_attack.values())
    assert {p for _, p in trial.single} == {p for _, p in trial.attack}


def test_organic_controls_include_single_project_donors():
    dev = synthetic_background(0)
    held = synthetic_background(100, heldout=True)
    assert len({u for u, _ in dev}) == len({u for u, _ in held}) == 240
    assert sum(len({p for donor, p in dev if donor == f"concentrated_organic_{i}"}) == 1 for i in range(40)) == 25
    assert sum(len({p for donor, p in held if donor == f"strong_organic_{i}"}) == 1 for i in range(50)) == 40


def test_vectorized_scores_match_full_path_in_pool_fraction():
    contributions = {("a", "p"): Decimal("0.13"), ("b", "p"): Decimal("0.27"),
                     ("c", "p"): Decimal("0.39"), ("a", "q"): Decimal("1.11"),
                     ("c", "q"): Decimal("2.13")}
    world = WorldCache(contributions, keys=[("G2", 10, 1.0)])
    matrix = world.feature_matrices["G2", 10, 1.0]
    beta = dict(beta0=-0.25, coh=0.8, conc=0.4, shapley=0.8, centrality=-0.3, size=0.5)
    for branch in ("size_only", "soft_base", "soft_shapley", "soft_centrality", "soft_full"):
        fast = matrix.score_many(branch, [beta], 10000)[0]
        lambdas = lambdas_for_branch(matrix.features, branch, beta, matrix.n_donors)
        raw = soft_discounting(contributions, matrix.communities, lambdas)
        slow = normalize(raw, 10000)[0]
        assert max(abs(fast[i]/10000-float(slow[p])/10000)
                   for i, p in enumerate(matrix.projects)) < 1e-12


def test_sparse_pairwise_and_coqf_match_reference():
    c = {("a", "p"): 4, ("b", "p"): 9, ("c", "p"): 16,
         ("a", "q"): 5, ("b", "q"): 7, ("c", "r"): 3}
    cached = PairwiseSparseCache(c)
    for tau in (1, 5, 500):
        expected = pairwise_qf(c, tau)
        assert max(abs(cached.score(tau)[p]-expected[p]) for p in expected) < 1e-12
    expected = coqf_paper2025_alg2(c)
    assert max(abs(coqf_default_fast(c)[p]-expected[p]) for p in expected) < 1e-12


def test_graph_family_equals_independent_build():
    c = {(f"u{i:02d}", "p"): 1 for i in range(50)}
    c.update({("u01", "q"): 1, ("u02", "q"): 1})
    for method in ("G1", "G2"):
        graphs, _ = graph_family(c, method)
        for k in (10, 20, 40):
            expected, _ = build_graph(c, method, k)
            assert set(map(frozenset, graphs[k].edges())) == set(map(frozenset, expected.edges()))


def test_suppression_undefined_and_zero_signflip():
    assert isnan(suppression(1, 1e-6*10000, 10000))
    assert paired_inference([0, 0, 0])["p_raw"] == 1.0
    adjusted = holm([{"p_raw": 0.01}, {"p_raw": 0.03}, {"p_raw": 0.5}])
    assert [x["p_holm"] for x in adjusted] == [0.03, 0.06, 0.5]
    assert unallocated(np.array([2500.0, 7500.000000000002]), 10000) == 0
