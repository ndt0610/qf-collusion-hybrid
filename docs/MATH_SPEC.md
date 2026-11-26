# MATH_SPEC v1.0 — Phase 1 locked specification

Status: locked by the project brief on 26 November 2026. Scope: donor–project donation data, graph features, raw matching mechanisms and allocation. Shapley and centrality are required ablation branches; no claim of fraud detection or superiority is assumed. All graph work is off chain. See `DATA_CARD.md` and `TRUST_MODEL.md` for limits.

## Data, units and allocation

Input event key is `(chain_id, round_id, donation_id)`. Keep original event fields and aggregate `c[u,p]` using Decimal **before** any square root, with `u=donor_address.lower()` and `p=project_id.lower()`. Retain events if USD is finite and strictly positive, application ID joins to the current `APPROVED` application for the same chain/round and project, and timestamp lies inclusively in the recorded donations window. Record all exclusion counts. The current application status may differ from historical status; do not infer historical eligibility from it. No Sybil label is present. Raw amounts are token base units; research QF uses the snapshot USD field. Direct donations remain separate from matching.

For nonnegative raw scores `R_p` and fixed matching pool `B`, `m_p=B R_p / Σ_q R_q` when the denominator is positive. If the denominator is zero, all `m_p=0` and `unallocated=B`. No per-project cap in v1. Float64 is used after Decimal aggregation for square roots; exact decimal aggregation does not make all computed scores exact.

For integer payout quotas, floor each quota, then assign leftover units by descending fractional remainder and ascending numeric `grant_id` for ties. `Σ payouts + unallocated = pool_amount` is mandatory. A future EVM test asset is independently denominated; USD is never relabelled as wei. If raw matching is zero, keep unallocated units instead of distributing them by largest remainder.

## Graphs and Louvain

Let `P_u={p:c[u,p]>0}`, `d_p=|{u:p∈P_u}|`, `ρ_p=1/ln(2+d_p)`.

- G1: `w_uv = Σ_{p∈P_u∩P_v}ρ_p / |P_u∪P_v|`.
- G2: `w_uv = Σ_{p∈P_u∩P_v}ρ_p`.

G1 is a custom rarity weighted overlap, not standard weighted Jaccard. G2 is a degree discounted common project score, not an exact claim of the original Adamic–Adar metric. Both score two donors who only support the same project by `ρ_p`, with no cosine cancellation.

For each donor, retain the top k positive-weight neighbors ordered by descending weight, then ascending donor ID. Symmetrize by union; an undirected edge exists if either endpoint chose the other, with the original symmetric weight. No self loops. Candidate accumulation is batched by donor (128 in the profile) and does not allocate a dense N×N matrix. Worst-case work still depends on `Σ_p d_p(d_p−1)/2`, and a single donor may have O(N) candidates. `k∈{10,20,40}`; Louvain `resolution∈{0.5,1,1.5}`, seeded and weighted. Graph method (G1/G2), k, resolution and seed are config, not learned from held-out results.

## Cluster features

For a fixed Louvain partition `C_1…C_K`, `a_kp=Σ_{u∈C_k}sqrt(c_up)`, `b_kp=Σ_{u∈C_k}c_up`, `A_p=Σ_k a_kp`.

`I_kp=a_kp²−b_kp`, `E_kp=a_kp(A_p−a_kp)`, `φ_kp=I_kp+E_kp`. This is the exact cluster Shapley allocation of **raw QF** with a fixed partition, computable in O(KP) after aggregation. `I` is intra-cluster matching amount, not a fraud amount. `S_k=Σ_p I_kp / Σ_p φ_kp` when denominator>0; otherwise `S_k=0` and flag `zero_matching_cluster`. Numerical cancellation near zero is clamped only for nonnegative amounts in implementation.

`cohesion_k=2W_int/(2W_int+W_ext)`, where weighted internal and boundary edges are counted once. Set 0 for singleton or zero denominator; do not call conductance. Let `P_p(C_k)=b_kp/Σ_q b_kq`. `proj_conc_k=1−H(P(C_k))/ln(|P_round|)`, where `H=−Σ P ln P`; set 0 for singleton, no money or <=1 project. This is concentration, not project exclusivity.

For each donor u within a cluster, `s_u=Σ_{v∈C_k}w_uv`. With `n=|C_k|`, `C_k^strength=(n Σ_u(s_u/Σ_v s_v)²−1)/(n−1)`. Set 0 and flag if singleton or total strength 0. This is a concentration of local weighted-degree centrality, not a Sybil score. A symmetric Sybil group may score low.

## Matching mechanisms and ablations

Standard QF: `R_p=(Σ_u sqrt(c_up))²−Σ_u c_up`.

Pairwise bounded QF from [Buterin 2019](https://ethresear.ch/t/pairwise-coordination-subsidies-a-new-quadratic-funding-design/5553): `T_uv=Σ_p sqrt(c_up c_vp)`, `k_uv=τ/(τ+T_uv)`, `R_p=2Σ_{u<v} k_uv sqrt(c_up c_vp)`. Tune `τ∈{1,5,25,100,500}` USD on dev. The per-pair raw-score bound `<2τ` does not automatically survive common fixed-pool scaling.

CO-QF is [Miller–Weyl–Kanich 2025 Algorithm 2](https://arxiv.org/html/2509.18343v1#S6), named `coqf_paper2025_alg2`: overlapping groups g are project supporter sets; `w_ig=c_ig/Σ_h c_ih`. For project p, sum over ordered `g≠h`:

`sqrt((Σ_{i∈g\h} c_ip w_ig)(Σ_{j∈h\g} c_jp w_jh))`.

No GPL Markov code is included. Results for this paper version cannot establish superiority over the distinct Gitcoin Markov COCM variant. Group memberships may also be supplied explicitly for hand tests.

HardCluster uses the same Louvain partition as soft methods and sets λ=1 for clusters with >=2 donors. Soft effective root `a_eff_kp=(1−λ_k)a_kp+λ_k sqrt(b_kp)`; `R_p=(Σ_k a_eff_kp)²−Σ_k b_kp`. Singletons always λ=0. This is split invariant only at λ=1 **inside an unchanged, correctly grouped cluster with each project total fixed**. The full graph/partition can change after an attack.

For larger clusters, `λ_k=clip(β0+βcoh*cohesion_k+βconc*proj_conc_k+βS*S_k+βC*C_k^strength,0,1)`. Grid: `β0∈{-0.5,-0.25,0}`, `βcoh,βconc∈{0,0.4,0.8}`, `βS∈{0,0.4,0.8,1.2}`, `βC∈{-0.6,-0.3,0,0.3,0.6}`. Branches `soft_base`, `soft_shapley`, `soft_centrality`, `soft_full` zero omitted coefficients. `size_only` instead uses `clip(β0+βsize ln|C_k|/ln N,0,1)`, `βsize∈{0.2,0.5,0.8,1.2}`. Tune every branch on dev with the same criterion. A zero coefficient means no contribution from that feature; the feature extraction itself may still be run for analysis.

## Phase 2 evaluation protocol, locked now

Empirical dev: Arbitrum `42161:27`. Inspect `42161:29`, `865`, `867` before freezing held-out assignment. Synthetic dev families: diverse organic, concentrated organic, pure split, three-project ring. Synthetic held-out families: in-budget decoy camouflage, cross-cluster split, four-project ring, strongly concentrated organic. All paired attack worlds keep the attacker budget and target set A fixed and recompute the whole graph and partition. `Δ_A=Σ_{p∈A}m_p(split)−Σ_{p∈A}m_p(single)`; report signed and positive part. Matching gain is not net profit.

For valid project set H without attack, `MechDamage(H)=Σ_{p∈H}max(0,m_p^Std−m_p^method)/Σ_{p∈H}m_p^Std`; specify behavior if denominator=0. Report median/P90 project loss and separate attack spillover on H. Policy damage threshold for dev selection is 5%; show sensitivity at 2%, 5%, 10%. This is a policy choice. Do not label unlabeled Gitcoin projects as honest ground truth. Trials in the same pool are dependent; significance testing must respect round/trial grouping.

## Phase 3 contract interface, locked now

Production leaf fields, in order: `(schemaVersion,chainId,vault,assetAddress,roundId,grantId,recipient,amount)` with ABI types `(uint256,uint256,address,address,uint256,uint256,address,uint256)` and OpenZeppelin StandardMerkleTree double hashing. Native asset sentinel is zero address. `publishRound(roundId,merkleRoot,claimDeadline)` is payable and immutable for that round; `sweepUnclaimed` is allowed after deadline. The actual vault, lifecycle, security tests and gas benchmark belong to Phase 3. A Merkle proof authenticates membership in a published payout table; it does not prove that the off-chain algorithm was correct.
