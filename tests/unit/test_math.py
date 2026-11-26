from collections import defaultdict
from itertools import permutations
from math import isclose, sqrt, log
import networkx as nx
import pytest

from qf_hybrid.features.core import extract
from qf_hybrid.graphs.core import build_graph, louvain
from qf_hybrid.mechanisms.core import (coqf_paper2025_alg2, hard_cluster,
    lambdas_for_branch, pairwise_qf, soft_discounting, standard_qf)


def test_exact_cluster_shapley_against_permutations():
    c = {(f"u{k}", p): x for k, row in enumerate([
        {"p": 1, "q": 4}, {"p": 9, "q": 1}, {"p": 4}, {"q": 16}]) for p, x in row.items()}
    groups = [{f"u{k}"} for k in range(4)]
    g = nx.Graph(); g.add_nodes_from(f"u{k}" for k in range(4))
    features = extract(c, g, groups)
    for p in ("p", "q"):
        def worth(members):
            amounts = [float(x) for (u, project), x in c.items() if project == p and u in members]
            return sum(sqrt(x) for x in amounts)**2 - sum(amounts)
        for k in range(4):
            marginal = []
            for order in permutations(range(4)):
                prior = {f"u{i}" for i in order[:order.index(k)]}
                marginal.append(worth(prior|{f"u{k}"})-worth(prior))
            assert abs(sum(marginal)/len(marginal)-features[k].phi[p]) < 1e-12


@pytest.mark.parametrize("n", [2, 3, 5, 8])
def test_exact_cluster_shapley_against_coalition_definition(n):
    from math import factorial
    c = {(f"u{i}", "p"): i+1 for i in range(n)}
    groups = [{f"u{i}"} for i in range(n)]
    g = nx.Graph(); g.add_nodes_from(f"u{i}" for i in range(n))
    features = extract(c, g, groups)
    def worth(mask):
        amounts = [i+1 for i in range(n) if mask & (1 << i)]
        return sum(sqrt(x) for x in amounts)**2-sum(amounts)
    for i in range(n):
        exact = 0.0
        for mask in range(1 << n):
            if mask & (1 << i):
                continue
            size = mask.bit_count()
            weight = factorial(size)*factorial(n-size-1)/factorial(n)
            exact += weight*(worth(mask | (1 << i))-worth(mask))
        assert abs(exact-features[i].phi["p"]) < 1e-12


def test_soft_endpoints_and_split_condition():
    c = {("a", "p"): 100, ("b", "p"): 25, ("c", "p"): 16}
    groups = [{"a", "b"}, {"c"}]
    assert soft_discounting(c, groups, [0, 0]) == standard_qf(c)
    assert soft_discounting(c, groups, [1, 1]) == hard_cluster(c, groups)
    one = {("a", "p"): 100, ("z", "p"): 25}
    split = {(f"s{i}", "p"): 10 for i in range(10)} | {("z", "p"): 25}
    before = soft_discounting(one, [{"a"}, {"z"}], [1, 0])["p"]
    after = soft_discounting(split, [{f"s{i}" for i in range(10)}, {"z"}], [1, 0])["p"]
    assert isclose(before, after, abs_tol=1e-12)
    assert soft_discounting(split, [{f"s{i}" for i in range(10)}, {"z"}], [0.5, 0])["p"] > before
    uneven = {("a", "p"): 0.13, ("b", "p"): 0.27, ("c", "p"): 0.39}
    assert soft_discounting(uneven, groups, [0, 0]) == standard_qf(uneven)


def test_pairwise_raw_bound_one_pair():
    c = {("a", "p"): 100, ("b", "p"): 100, ("a", "q"): 1, ("b", "q"): 4}
    tau = 5
    result = pairwise_qf(c, tau)
    assert isclose(result["p"], 2*100*5/(5+102))
    assert sum(result.values()) < 2*tau


def test_coqf_overlap_hand_example_and_disjoint_reduction():
    c = {("a", "p"): 4, ("b", "p"): 9, ("c", "p"): 16}
    m = {"a": {"X": 1}, "b": {"X": 0.5, "Y": 0.5}, "c": {"Y": 1}}
    # Only a in X\Y and c in Y\X contribute. b belongs to both and is excluded.
    assert isclose(coqf_paper2025_alg2(c, m)["p"], 2*sqrt(4*16))
    disjoint = {"a": {"X": 1}, "b": {"X": 1}, "c": {"Y": 1}}
    expected = hard_cluster(c, [{"a", "b"}, {"c"}])
    assert isclose(coqf_paper2025_alg2(c, disjoint)["p"], expected["p"])


def test_feature_boundary_and_branches():
    c = {("a", "p"): 1, ("b", "p"): 1, ("c", "q"): 4}
    g = nx.Graph(); g.add_nodes_from(("a", "b", "c")); g.add_edge("a", "b", weight=0.5)
    features = extract(c, g, [{"a", "b"}, {"c"}])
    assert isclose(features[0].cohesion, 1)
    assert isclose(features[0].shapley_share, 1)
    assert features[1].centrality == 0
    assert "singleton" in features[1].flags
    beta = {"beta0": 0, "coh": 0, "conc": 0, "shapley": 0.8, "centrality": 0.6}
    assert lambdas_for_branch(features, "soft_base", beta, 3)[0] == 0
    assert isclose(lambdas_for_branch(features, "soft_shapley", beta, 3)[0], 0.8)
    assert lambdas_for_branch(features, "soft_full", beta, 3)[1] == 0
