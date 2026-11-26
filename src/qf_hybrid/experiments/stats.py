"""Trial-level paired bootstrap, sign flips, and Holm correction."""
import itertools
import numpy as np


def paired_inference(differences, seed=2026, boot_reps=10_000, perm_reps=100_000):
    d = np.asarray(differences, dtype=float).copy()
    if d.ndim != 1 or len(d) == 0 or not np.all(np.isfinite(d)):
        raise ValueError("Need finite paired differences")
    d[np.abs(d) < 1e-12] = 0.0  # pool-fraction numerical zero
    n = len(d)
    if np.all(d == 0):
        return dict(n=n, mean_diff=0.0, median_diff=0.0, ci_low=0.0, ci_high=0.0, p_raw=1.0)
    rng = np.random.default_rng(seed)
    draws = rng.integers(0, n, size=(boot_reps, n))
    means = d[draws].mean(axis=1)
    low, high = np.quantile(means, [0.025, 0.975])
    observed = abs(d.mean())
    nonzero = d[d != 0]
    if len(nonzero) <= 16:
        flipped = np.array([abs(np.sum(nonzero*np.array(signs))/n) for signs in itertools.product((-1, 1), repeat=len(nonzero))])
        p = float(np.mean(flipped >= observed-1e-15))
    else:
        signs = rng.choice((-1.0, 1.0), size=(perm_reps, len(nonzero)))
        flipped = np.abs((signs*nonzero).sum(axis=1)/n)
        p = float((np.count_nonzero(flipped >= observed-1e-15)+1)/(perm_reps+1))
    return dict(n=n, mean_diff=float(d.mean()), median_diff=float(np.median(d)),
                ci_low=float(low), ci_high=float(high), p_raw=p)


def holm(rows):
    """Adjust within one predeclared comparison family."""
    ordering = sorted(range(len(rows)), key=lambda i: rows[i]["p_raw"])
    previous = 0.0
    for rank, index in enumerate(ordering):
        previous = max(previous, min(1.0, rows[index]["p_raw"]*(len(rows)-rank)))
        rows[index]["p_holm"] = previous
    return rows
