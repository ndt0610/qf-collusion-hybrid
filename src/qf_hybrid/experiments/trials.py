"""World-local graph and feature caches; no state crosses paired worlds."""
from dataclasses import dataclass
from time import perf_counter
import numpy as np

from qf_hybrid.features.core import extract
from qf_hybrid.graphs.core import graph_family, louvain
from qf_hybrid.mechanisms.core import (PairwiseSparseCache, coqf_default_fast,
    hard_cluster, standard_qf)

GRAPH_KEYS = tuple((method, k, resolution)
                   for method in ("G1", "G2") for k in (10, 20, 40)
                   for resolution in (0.5, 1.0, 1.5))


def _normalize_array(scores, pool):
    scores = np.maximum(scores, 0.0)
    denom = scores.sum(axis=-1, keepdims=True)
    return np.divide(scores*pool, denom, out=np.zeros_like(scores), where=denom > 0)


@dataclass
class FeatureMatrix:
    projects: list[str]
    features: list
    communities: list

    def __post_init__(self):
        self.a = np.array([[f.a.get(p, 0.0) for p in self.projects] for f in self.features])
        self.b = np.array([[f.b.get(p, 0.0) for p in self.projects] for f in self.features])
        self.sqrt_b = np.sqrt(self.b)
        self.total_b = self.b.sum(axis=0)
        self.coh = np.array([f.cohesion for f in self.features])
        self.conc = np.array([f.proj_conc for f in self.features])
        self.shapley = np.array([f.shapley_share for f in self.features])
        self.centrality = np.array([f.centrality for f in self.features])
        self.sizes = np.array([len(f.donors) for f in self.features])
        self.n_donors = int(self.sizes.sum())

    def score_many(self, branch, betas, pool):
        if not betas:
            return np.empty((0, len(self.projects)))
        coeff = lambda name: np.array([row.get(name, 0.0) for row in betas])[:, None]
        lam = coeff("beta0") + np.zeros((len(betas), len(self.features)))
        if branch == "size_only":
            size_term = np.log(self.sizes)/np.log(max(2, self.n_donors))
            lam += coeff("size")*size_term[None, :]
        else:
            lam += coeff("coh")*self.coh[None, :] + coeff("conc")*self.conc[None, :]
            if branch in ("soft_shapley", "soft_full"):
                lam += coeff("shapley")*self.shapley[None, :]
            if branch in ("soft_centrality", "soft_full"):
                lam += coeff("centrality")*self.centrality[None, :]
        np.clip(lam, 0, 1, out=lam)
        lam[:, self.sizes <= 1] = 0
        roots = (self.a[None, :, :] + lam[:, :, None]*(self.sqrt_b-self.a)[None, :, :]).sum(axis=1)
        raw = np.maximum(0.0, roots**2-self.total_b[None, :])
        return _normalize_array(raw, pool)


class WorldCache:
    def __init__(self, contributions, keys=GRAPH_KEYS, seed=42):
        self.contributions = contributions
        self.projects = sorted({p for _, p in contributions})
        self.keys = tuple(keys)
        self.feature_matrices = {}
        self.graph_seconds = 0.0
        requested = {method for method, _, _ in self.keys}
        for method in sorted(requested):
            started = perf_counter()
            graphs, _ = graph_family(contributions, method)
            self.graph_seconds += perf_counter()-started
            for _, k, resolution in (key for key in self.keys if key[0] == method):
                groups = louvain(graphs[k], resolution=resolution, seed=seed)
                features = extract(contributions, graphs[k], groups)
                self.feature_matrices[method, k, resolution] = FeatureMatrix(self.projects, features, groups)
        self._pairwise = None

    def soft(self, key, branch, betas, pool):
        return self.feature_matrices[key].score_many(branch, betas, pool)

    def baseline(self, method, pool, *, tau=5, hard_key=None):
        if method == "standard_qf":
            raw = standard_qf(self.contributions)
        elif method == "pairwise_qf":
            if self._pairwise is None:
                self._pairwise = PairwiseSparseCache(self.contributions)
            raw = self._pairwise.score(tau)
        elif method == "coqf_paper2025_alg2":
            raw = coqf_default_fast(self.contributions)
        elif method == "hard_cluster":
            raw = hard_cluster(self.contributions, self.feature_matrices[hard_key].communities)
        else:
            raise ValueError(method)
        return _normalize_array(np.array([raw.get(p, 0.0) for p in self.projects]), pool)
