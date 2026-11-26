"""Unnormalized matching scores; normalize once across projects in allocation."""
from collections import defaultdict
from math import log, sqrt
import numpy as np
from scipy import sparse


def _validate(contributions):
    for amount in contributions.values():
        if amount < 0:
            raise ValueError("Negative contribution")


def standard_qf(contributions):
    _validate(contributions)
    roots = defaultdict(float)
    totals = defaultdict(float)
    for (_, p), amount in contributions.items():
        roots[p] += sqrt(float(amount))
        totals[p] += float(amount)
    return {p: max(0.0, roots[p]**2-totals[p]) for p in sorted(totals)}


def pairwise_qf(contributions, tau):
    _validate(contributions)
    if tau <= 0:
        raise ValueError("tau must be positive")
    by_project = defaultdict(list)
    by_pair = defaultdict(float)
    for (u, p), amount in contributions.items():
        by_project[p].append((u, sqrt(float(amount))))
    for p, donors in by_project.items():
        donors.sort()
        for i, (u, a) in enumerate(donors):
            for v, b in donors[i+1:]:
                by_pair[u, v] += a*b
    result = {p: 0.0 for p in sorted(by_project)}
    for p, donors in by_project.items():
        for i, (u, a) in enumerate(donors):
            for v, b in donors[i+1:]:
                result[p] += 2*a*b*tau/(tau+by_pair[u, v])
    return result


class PairwiseSparseCache:
    """Sparse donor Gram matrix reused for the locked tau grid."""
    def __init__(self, contributions):
        self.donors = sorted({u for u, _ in contributions})
        self.projects = sorted({p for _, p in contributions})
        ui = {u: i for i, u in enumerate(self.donors)}
        pi = {p: i for i, p in enumerate(self.projects)}
        rows, cols, values = [], [], []
        for (u, p), amount in contributions.items():
            if amount > 0:
                rows.append(ui[u]); cols.append(pi[p]); values.append(sqrt(float(amount)))
        self.x = sparse.csr_matrix((values, (rows, cols)), shape=(len(ui), len(pi)))
        self.t = (self.x @ self.x.T).tocsr()
        self.t.setdiag(0)
        self.t.eliminate_zeros()

    def score(self, tau):
        if tau <= 0:
            raise ValueError("tau must be positive")
        kernel = self.t.copy()
        kernel.data = tau/(tau+kernel.data)
        values = np.asarray(self.x.multiply(kernel @ self.x).sum(axis=0)).ravel()
        return dict(zip(self.projects, values.tolist()))


def coqf_default_fast(contributions):
    """Default project-membership CO-QF via donor support tensors."""
    projects = sorted({p for _, p in contributions})
    index = {p: i for i, p in enumerate(projects)}
    n = len(projects)
    main = np.zeros((n, n), dtype=float)
    overlap = np.zeros((n, n, n), dtype=float)
    by_donor = defaultdict(dict)
    for (u, p), amount in contributions.items():
        if amount > 0:
            by_donor[u][p] = float(amount)
    for row in by_donor.values():
        total = sum(row.values())
        items = [(index[p], amount, amount/total) for p, amount in row.items()]
        for p, amount, _ in items:
            for g, _, weight in items:
                value = amount*weight
                main[p, g] += value
                for h, _, _ in items:
                    overlap[p, g, h] += value
    left = np.maximum(0.0, main[:, :, None] - overlap)
    right = np.maximum(0.0, main[:, None, :] - overlap.transpose(0, 2, 1))
    terms = np.sqrt(left*right)
    for p in range(n):
        np.fill_diagonal(terms[p], 0.0)
    return {p: float(terms[i].sum()) for i, p in enumerate(projects)}


def coqf_paper2025_alg2(contributions, memberships=None):
    """Miller-Weyl-Kanich (2025), Algorithm 2; ordered distinct group pairs.

    memberships[u] maps group -> nonnegative membership, normalized per donor.
    If omitted, each project is a group, weighted by donor money to that project.
    """
    _validate(contributions)
    by_donor = defaultdict(dict)
    projects = sorted({p for _, p in contributions})
    for (u, p), amount in contributions.items():
        by_donor[u][p] = float(amount)
    if memberships is None:
        memberships = {}
        for u, row in by_donor.items():
            total = sum(row.values())
            memberships[u] = {p: amount/total for p, amount in row.items() if amount > 0} if total else {}
    groups = sorted({g for row in memberships.values() for g in row})
    normalized = {}
    for u in by_donor:
        row = memberships.get(u, {})
        if any(w < 0 for w in row.values()):
            raise ValueError("Negative membership")
        total = sum(row.values())
        normalized[u] = {g: w/total for g, w in row.items() if w > 0} if total else {}
    active = {p: [(u, by_donor[u][p], normalized[u]) for u in by_donor if by_donor[u].get(p, 0) > 0] for p in projects}
    scores = {p: 0.0 for p in projects}
    for p in projects:
        for gi, g in enumerate(groups):
            for h in groups[gi+1:]:
                left = sum(amount*row[g] for _, amount, row in active[p] if g in row and h not in row)
                right = sum(amount*row[h] for _, amount, row in active[p] if h in row and g not in row)
                scores[p] += 2*sqrt(left*right)
    return scores


def hard_cluster(contributions, communities):
    return soft_discounting(contributions, communities, [1.0]*len(communities))


def soft_discounting(contributions, communities, lambdas):
    _validate(contributions)
    if len(communities) != len(lambdas):
        raise ValueError("Community/lambda length mismatch")
    if any(not 0 <= float(value) <= 1 for value in lambdas):
        raise ValueError("lambda outside [0,1]")
    membership = {u: k for k, group in enumerate(communities) for u in group}
    if len(membership) != sum(len(group) for group in communities):
        raise ValueError("Overlapping communities")
    if membership.keys() != {u for u, _ in contributions}:
        raise ValueError("Missing donor in communities")
    if all(float(lambdas[k]) == 0 or len(group) <= 1 for k, group in enumerate(communities)):
        return standard_qf(contributions)
    a, b = defaultdict(float), defaultdict(float)
    for (u, p), amount in contributions.items():
        key = (membership[u], p)
        a[key] += sqrt(float(amount))
        b[key] += float(amount)
    projects = sorted({p for _, p in contributions})
    result = {}
    for p in projects:
        effective = 0.0
        total = 0.0
        for k, group in enumerate(communities):
            lam = float(lambdas[k])
            if len(group) <= 1:
                lam = 0.0
            effective += (1-lam)*a[k,p] + lam*sqrt(b[k,p])
            total += b[k,p]
        result[p] = max(0.0, effective**2-total)
    return result


BETA_GRID = {
    "beta0": (-0.5, -0.25, 0.0), "coh": (0.0, 0.4, 0.8),
    "conc": (0.0, 0.4, 0.8), "shapley": (0.0, 0.4, 0.8, 1.2),
    "centrality": (-0.6, -0.3, 0.0, 0.3, 0.6),
    "size": (0.2, 0.5, 0.8, 1.2),
}
BRANCHES = ("size_only", "soft_base", "soft_shapley", "soft_centrality", "soft_full")


def lambdas_for_branch(features, branch, beta, total_donors):
    if branch not in BRANCHES:
        raise ValueError("Unknown branch")
    out = []
    for f in features:
        if len(f.donors) <= 1:
            out.append(0.0)
            continue
        value = beta.get("beta0", 0.0)
        if branch == "size_only":
            value += beta.get("size", 0.0)*log(len(f.donors))/log(total_donors)
        else:
            value += beta.get("coh", 0.0)*f.cohesion + beta.get("conc", 0.0)*f.proj_conc
            if branch in ("soft_shapley", "soft_full"):
                value += beta.get("shapley", 0.0)*f.shapley_share
            if branch in ("soft_centrality", "soft_full"):
                value += beta.get("centrality", 0.0)*f.centrality
        out.append(min(1.0, max(0.0, value)))
    return out
