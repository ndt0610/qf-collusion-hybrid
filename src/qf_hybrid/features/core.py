"""Exact cluster QF accounting and descriptive graph features."""
from collections import defaultdict
from dataclasses import dataclass
from math import log, sqrt


@dataclass
class ClusterFeatures:
    donors: frozenset[str]
    a: dict[str, float]
    b: dict[str, float]
    intra: dict[str, float]
    inter: dict[str, float]
    phi: dict[str, float]
    shapley_share: float
    cohesion: float
    proj_conc: float
    centrality: float
    flags: frozenset[str]


def extract(contributions, graph, communities):
    donors = {u for u, _ in contributions}
    all_members = [u for group in communities for u in group]
    if len(set(all_members)) != len(all_members) or set(all_members) != donors:
        raise ValueError("Communities must partition all contributing donors")
    projects = sorted({p for _, p in contributions})
    by_donor = {u: index for index, group in enumerate(communities) for u in group}
    a = [defaultdict(float) for _ in communities]
    b = [defaultdict(float) for _ in communities]
    for (u, p), amount in contributions.items():
        if amount < 0:
            raise ValueError("Negative contribution")
        k = by_donor[u]
        a[k][p] += sqrt(float(amount))
        b[k][p] += float(amount)
    total_a = {p: sum(row[p] for row in a) for p in projects}
    internal = [0.0 for _ in communities]
    boundary = [0.0 for _ in communities]
    strengths = [defaultdict(float) for _ in communities]
    for u, v, data in graph.edges(data=True):
        ku, kv = by_donor[u], by_donor[v]
        weight = data["weight"]
        if ku == kv:
            internal[ku] += weight
            strengths[ku][u] += weight
            strengths[ku][v] += weight
        else:
            boundary[ku] += weight
            boundary[kv] += weight
    output = []
    for k, group in enumerate(communities):
        flags = set()
        intra = {p: max(0.0, a[k][p]**2 - b[k][p]) for p in projects}
        inter = {p: a[k][p] * (total_a[p] - a[k][p]) for p in projects}
        phi = {p: intra[p] + inter[p] for p in projects}
        denom = sum(phi.values())
        share = sum(intra.values()) / denom if denom > 0 else 0.0
        if denom == 0:
            flags.add("zero_matching_cluster")
        if len(group) <= 1:
            cohesion = concentration = centrality = 0.0
            flags.add("singleton")
        else:
            coh_denom = 2*internal[k] + boundary[k]
            cohesion = 2*internal[k]/coh_denom if coh_denom else 0.0
            money = sum(b[k].values())
            if len(projects) <= 1 or money <= 0:
                concentration = 0.0
                flags.add("undefined_project_concentration")
            else:
                import math
                entropy = -sum((x/money)*math.log(x/money) for x in b[k].values() if x > 0)
                concentration = 1 - entropy/log(len(projects))
            group_strengths = [strengths[k][u] for u in group]
            total_strength = sum(group_strengths)
            if total_strength == 0:
                centrality = 0.0
                flags.add("zero_internal_strength")
            else:
                n = len(group)
                centrality = (n * sum((s/total_strength)**2 for s in group_strengths)-1)/(n-1)
        output.append(ClusterFeatures(frozenset(group), dict(a[k]), dict(b[k]), intra, inter, phi,
                                      share, cohesion, concentration, centrality, frozenset(flags)))
    return output
