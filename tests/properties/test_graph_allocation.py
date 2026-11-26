from decimal import Decimal
from math import isclose, log
import pytest

from qf_hybrid.allocation.core import apportion, manifest, normalize
from qf_hybrid.graphs.core import build_graph
from qf_hybrid.mechanisms.core import standard_qf


@pytest.mark.parametrize("method", ["G1", "G2"])
def test_graph_single_shared_project_rarity_and_order(method):
    c = {("a", "p"): 1, ("b", "p"): 4, ("c", "q"): 5}
    first, _ = build_graph(c, method, k=1, batch_size=1)
    reverse, _ = build_graph(dict(reversed(list(c.items()))), method, k=1, batch_size=2)
    expected = 1/log(4)
    assert isclose(first["a"]["b"]["weight"], expected)
    assert first.number_of_edges() == 1
    assert not any(u == v for u, v in first.edges)
    assert first["a"]["b"]["weight"] == first["b"]["a"]["weight"]
    assert list(first.edges(data=True)) == list(reverse.edges(data=True))


def test_graph_topk_union_and_tie_break():
    c = {(u, "p"): 1 for u in ("a", "b", "c")}
    graph, stats = build_graph(c, "G2", k=1)
    assert set(map(frozenset, graph.edges())) == {frozenset(("a", "b")), frozenset(("a", "c"))}
    assert stats["candidate_undirected"] == 3


def test_aggregate_before_square_root():
    from collections import defaultdict
    events = [("a", "p", Decimal("1.25")), ("a", "p", Decimal("2.75")), ("b", "p", Decimal("4"))]
    grouped = defaultdict(Decimal)
    for u, p, amount in events:
        grouped[u, p] += amount
    assert grouped["a", "p"] == Decimal("4.00")
    assert standard_qf(grouped) == standard_qf({("a", "p"): Decimal("4"), ("b", "p"): Decimal("4")})


def test_normalize_zero_and_largest_remainder():
    quotas, unallocated = normalize({"1": 0, "2": 0}, 5)
    assert unallocated == 5
    assert apportion(quotas, 5, unallocated) == {"1": 0, "2": 0}
    quotas, unallocated = normalize({"2": 1, "1": 1, "3": 1}, 2)
    assert apportion(quotas, 2) == {"2": 1, "1": 1, "3": 0}
    assert sum(apportion(quotas, 2).values())+unallocated == 2
    assert apportion({"1": Decimal("0.5"), "2": Decimal("0.5")}, 1) == {"1": 1, "2": 0}


def test_manifest_schema_and_pool():
    x = manifest(round_id=7,chain_id=31337,vault="0x"+"1"*40,asset_address="0x"+"0"*40,
        decimals=18,pool_amount=5,payouts={"2": 3,"1": 1},recipients={"2":"0x"+"2"*40,"1":"0x"+"3"*40},
        data_sha256="a"*64,config_sha256="b"*64,unallocated=1)
    assert x["payouts"][0]["grant_id"] == "1"
    assert x["leaf_abi_types"] == ["uint256","uint256","address","address","uint256","uint256","address","uint256"]
    with pytest.raises(ValueError):
        manifest(round_id=7,chain_id=31337,vault="0x"+"1"*40,asset_address="0x"+"0"*40,
            decimals=18,pool_amount=3,payouts={"2": 3,"1": 1},recipients={"2":"0x"+"2"*40,"1":"0x"+"3"*40},
            data_sha256="a"*64,config_sha256="b"*64,unallocated=1)
