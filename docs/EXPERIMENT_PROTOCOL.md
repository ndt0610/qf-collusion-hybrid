# Phase 2 experiment protocol — locked before held-out evaluation

The two Phase 2 briefs supplied by the owner are identical. This file fixes operational interpretations and evaluation order. Phase 1 `MATH_SPEC.md` remains binding. No EVM deployment or gas measurement is in scope.

## Split, units, seeds

Empirical dev is `42161:27`; empirical held-out is `42161:865` and `42161:867`; same-season sensitivity is `42161:29`. All share one portal snapshot and have no Sybil ground truth. Empirical projects outside injected target set A are `background/non-target`, never asserted honest. Synthetic dev and held-out generator families are disjoint. Seed indices 0–5 are dev and 100–109 held-out; empirical seeds are 1000–1004 (dev) and 2000–2004 (held-out and sensitivity). Every published trial row records its seed.

Synthetic fixed research matching pool B = USD 10,000; empirical B = USD 100,000. These are counterfactual comparison budgets, not historical Gitcoin pools. All money metrics include USD and `pct_pool=value/B`. Direct donations are excluded from matching allocations. Each world is normalized independently to the same B. Zero raw total leaves the entire B unallocated.

## Worlds and labels

Synthetic backgrounds have 24 valid projects and 240 legitimate wallets. Dev contains 165 Zipf-distributed diverse donors, a 35-donor diverse organic group, and a 40-donor concentrated organic group (25 single-project donors). Held-out contains 165 diverse donors, 25 additional diverse donors, and a 50-donor strongly concentrated group (40 single-project donors). The extra 25 resolve the brief's 165+50 versus 240 count without reusing a dev hard-negative family. All synthetic projects are known valid by construction; `H` denotes these 24, including organic targets.

Attack families and budgets are exactly those in the signed brief. Split and comparator worlds share the same background, exact attacker budget, and exact attacker contribution by project. For ring attacks the comparator has one separate donor per team, rather than one merged donor. Synthetic `ring_4proj` uses a seed-specific cyclic allocation of each team's USD 180 across four targets and USD 20 on one common decoy; the cyclic column sums are also USD 180, so the comparator contributes USD 180 to its own target and USD 20 to the decoy. `cross_cluster_split` uses 75% on the target and 25% divided equally over eight background projects forming four disjoint pairs. The wording “25% ... into a pair” is interpreted as 25% across all four pairs, preserving the stated total D.

Empirical attacks inject new target projects and add attacker donations to a filtered, unchanged round. D = max(USD 500, 0.02 × filtered round USD). Four highest-total background projects are decoys for camouflage; eight highest-total background projects form distinct cross-cluster decoy pairs. These are protocol choices, not labels. Rebuild graph, Louvain partition, features, scores, and pool allocation separately in every paired world. Reuse only within-world graph candidate weights for k=10/20/40 and within-partition feature matrices across beta candidates. HardCluster uses the topology frozen for `soft_full` at δ=5%; it has no separately tuned parameters.

## Tuning and statistics

Graph grid: G1/G2 × k=10/20/40 × resolution=0.5/1/1.5; seed=42. Soft beta grid and pairwise tau grid are in `MATH_SPEC.md`. A candidate's `dev_mech_damage` is the mean over six attack-free synthetic dev backgrounds. A candidate's `dev_attack_gain` is the equally weighted mean of family means of positive target allocation gain/B across synthetic dev and empirical dev families. Among candidates with damage ≤δ, minimize gain, then damage, beta L1 norm, G1 before G2, smaller k, and resolution closer to 1. If infeasible, minimize damage and mark it. Freeze selected configurations for δ=2%, 5%, 10% before reading any held-out round. The main held-out run evaluates the nine mechanisms at δ=5% only.

Synthetic attack-free damage uses project-wise positive deficits versus Standard QF and reports median/P90 project loss. Empirical attack-free difference from Standard on background is descriptive, never `MechDamage(H)`. Attack spillover compares background allocation in paired worlds within one method, as absolute and positive-loss sums. Target gain Δ_A is signed; suppression uses signed Δ_A and is undefined if Standard Δ_A≤10⁻⁶B. `unallocated_pct` is reported for each world. Organic controls are evaluated without an attack and have no Δ_A.

Held-out inferential comparisons use synthetic held-out paired *trials*, grouped by seed and family, as the sampling unit; empirical rounds are reported descriptively because two held-out rounds plus sensitivity do not constitute independent samples. Direction for `mean_diff` is first method's positive target gain/B minus second's, so negative favors the first. Paired bootstrap draws 10,000 resamples with fixed seed; two-sided paired sign-flip uses exact enumeration when n≤16 and seeded Monte Carlo otherwise, with Holm correction within four ablation and four baseline comparisons. Family-level dependence and synthetic generator assumptions limit inference.

`configs/heldout/frozen_mechanisms.json` is written by the dev script before the held-out script loads it. The latter reads no dev selection tables and performs no fitting. `plot_phase2.py` reads saved CSV only.
