"""Exact sparse candidate accumulation, with bounded donor batches.

No dense N-by-N matrix is created. High-degree projects still induce many pairs.
"""
from collections import defaultdict
from math import log
from time import perf_counter
import networkx as nx


def project_index(contributions):
    by_project = defaultdict(set)
    by_donor = defaultdict(set)
    for (donor, project), amount in contributions.items():
        if amount > 0:
            by_project[project].add(donor)
            by_donor[donor].add(project)
    by_project = {p: sorted(us) for p, us in by_project.items()}
    return by_project, {u: sorted(ps) for u, ps in by_donor.items()}


def pair_work(contributions):
    projects, _ = project_index(contributions)
    return sum(len(us) * (len(us)-1) // 2 for us in projects.values())


def build_graph(contributions, method="G1", k=20, batch_size=128, return_selected=False):
    if method not in ("G1", "G2") or k < 1 or batch_size < 1:
        raise ValueError("Invalid graph parameters")
    started = perf_counter()
    by_project, by_donor = project_index(contributions)
    donors = sorted(by_donor)
    weights = {p: 1.0 / log(2 + len(us)) for p, us in by_project.items()}
    selected = {}
    candidate_counts = 0
    for base in range(0, len(donors), batch_size):
        for u in donors[base:base + batch_size]:
            overlaps = defaultdict(float)
            common_counts = defaultdict(int)
            for p in by_donor[u]:
                rho = weights[p]
                for v in by_project[p]:
                    if v != u:
                        overlaps[v] += rho
                        common_counts[v] += 1
            candidate_counts += len(overlaps)
            ranked = []
            for v, shared in overlaps.items():
                if method == "G1":
                    union = len(by_donor[u]) + len(by_donor[v]) - common_counts[v]
                    value = shared / union
                else:
                    value = shared
                if value > 0:
                    ranked.append((v, value))
            ranked.sort(key=lambda item: (-item[1], item[0]))
            selected[u] = ranked[:k]
    graph = nx.Graph()
    graph.add_nodes_from(donors)
    edge_counts = {}
    for cutoff in (10, 20, 40):
        if cutoff <= k:
            pairs = {tuple(sorted((u, v))) for u in donors for v, _ in selected[u][:cutoff]}
            edge_counts[str(cutoff)] = len(pairs)
    for u in donors:
        for v, weight in selected[u]:
            graph.add_edge(u, v, weight=weight)
    stats = {"method": method, "k": k, "donors": len(donors),
                   "candidate_directed": candidate_counts,
                   "candidate_undirected": candidate_counts // 2,
                   "edges_by_k_union": edge_counts,
                   "edges_after_topk_union": graph.number_of_edges(),
                   "seconds": perf_counter()-started,
                   "pair_work_with_multiplicity": pair_work(contributions)}
    if return_selected:
        stats["selected"] = selected
    return graph, stats


def graph_family(contributions, method="G1", batch_size=128):
    """One candidate ranking gives exact union graphs for all locked k values."""
    _, stats = build_graph(contributions, method, 40, batch_size, return_selected=True)
    selected = stats.pop("selected")
    graphs = {}
    for cutoff in (10, 20, 40):
        graph = nx.Graph()
        graph.add_nodes_from(sorted(selected))
        for u, neighbors in selected.items():
            for v, weight in neighbors[:cutoff]:
                graph.add_edge(u, v, weight=weight)
        graphs[cutoff] = graph
    return graphs, stats


def louvain(graph, resolution=1.0, seed=42):
    if graph.number_of_edges() == 0:
        return [{u} for u in sorted(graph)]
    groups = nx.community.louvain_communities(graph, weight="weight", resolution=resolution, seed=seed)
    return [set(group) for group in sorted(groups, key=lambda group: min(group))]
