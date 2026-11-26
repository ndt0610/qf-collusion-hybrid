"""Pool-level metrics with explicit label and denominator semantics."""
import math
import numpy as np


def damage(standard, method, projects, valid):
    indices = [projects.index(p) for p in sorted(valid)]
    baseline = np.asarray(standard)[indices]
    actual = np.asarray(method)[..., indices]
    losses = np.divide(np.maximum(0, baseline-actual), baseline,
                       out=np.zeros_like(actual), where=baseline > 0)
    total = baseline.sum()
    aggregate = np.maximum(0, baseline-actual).sum(axis=-1)/total if total > 0 else np.zeros(actual.shape[:-1])
    return aggregate, np.median(losses, axis=-1), np.percentile(losses, 90, axis=-1)


def attack_gain(single, attack, projects, targets, pool):
    indices = [projects.index(p) for p in sorted(targets)]
    signed = np.asarray(attack)[..., indices].sum(axis=-1)-np.asarray(single)[..., indices].sum(axis=-1)
    return signed, np.maximum(0, signed), signed/pool, np.maximum(0, signed)/pool


def suppression(delta_method, delta_standard, pool):
    if delta_standard <= 1e-6*pool:
        return math.nan
    return 1-delta_method/delta_standard


def spillover(single, attack, projects, targets, pool):
    indices = [i for i, p in enumerate(projects) if p not in targets]
    difference = np.asarray(attack)[..., indices]-np.asarray(single)[..., indices]
    return (np.abs(difference).sum(axis=-1), np.maximum(0, -difference).sum(axis=-1),
            np.abs(difference).sum(axis=-1)/pool, np.maximum(0, -difference).sum(axis=-1)/pool)


def diff_vs_standard(standard, method, projects, targets, pool):
    indices = [i for i, p in enumerate(projects) if p not in targets]
    difference = np.asarray(method)[..., indices]-np.asarray(standard)[..., indices]
    return float(np.abs(difference).sum()), float(np.abs(difference).sum()/pool)


def unallocated(alloc, pool):
    gap = pool-float(np.asarray(alloc).sum())
    return 0.0 if abs(gap) <= 1e-10*pool else max(0.0, gap)
