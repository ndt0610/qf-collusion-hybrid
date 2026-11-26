# Phase 5.2 handoff

## Frozen Phase 1–2 artifacts

SHA-256 before and after Phase 5.2 matches for all 13 scoped artifacts. No Phase 1/2 experiment was rerun.

| Artifact | SHA-256 before | SHA-256 after |
|---|---|---|
| `configs/heldout/frozen_mechanisms.json` | `b1aff86f0052829b8decc62100016bcebc017e241f0278bbf853827d04fa48c5` | `b1aff86f0052829b8decc62100016bcebc017e241f0278bbf853827d04fa48c5` |
| `results/figures/fig01_tradeoff_frontier_dev.png` | `763e804efe877fe15ddb9c26261965a5a94d73b5af271f3edf821ae820a9d1ba` | `763e804efe877fe15ddb9c26261965a5a94d73b5af271f3edf821ae820a9d1ba` |
| `results/figures/fig02_heldout_synthetic_ablation.png` | `a18b64498fab6203956029950927e4eb819f39789d46270e5fb16a262c043a0c` | `a18b64498fab6203956029950927e4eb819f39789d46270e5fb16a262c043a0c` |
| `results/figures/fig03_heldout_empirical_gitcoin.png` | `b05d734176984dfed6bcdb5b48586e5a1878afe2b0eba3545ff90a7927090b39` | `b05d734176984dfed6bcdb5b48586e5a1878afe2b0eba3545ff90a7927090b39` |
| `results/tables/phase1_data_graph_profile.csv` | `796e4437a446b7c46867d5508b7aa15a71d6ba472262e52399a94f0487b95d33` | `796e4437a446b7c46867d5508b7aa15a71d6ba472262e52399a94f0487b95d33` |
| `results/tables/phase2_dev_frontier.csv` | `0d2883c7e2744b8a5d4db793701f52bd0cc101953ff251832f4b83616a413af6` | `0d2883c7e2744b8a5d4db793701f52bd0cc101953ff251832f4b83616a413af6` |
| `results/tables/phase2_dev_pareto.csv` | `17ecd6de87c0fb1f5cb3504fd5bb85f1ffa050ac9e584a4bcf06b1725ce92494` | `17ecd6de87c0fb1f5cb3504fd5bb85f1ffa050ac9e584a4bcf06b1725ce92494` |
| `results/tables/phase2_dev_selection.csv` | `cd516b7f214aaadcc820bb1db6a6cbc870648f373164f387c8c819c04876e416` | `cd516b7f214aaadcc820bb1db6a6cbc870648f373164f387c8c819c04876e416` |
| `results/tables/phase2_heldout_empirical.csv` | `cf2157b9fc67c4ee84ea49ff60b4cfc67024b29267ef80cc9fc0dee93959cffb` | `cf2157b9fc67c4ee84ea49ff60b4cfc67024b29267ef80cc9fc0dee93959cffb` |
| `results/tables/phase2_heldout_synthetic.csv` | `f73a991e4b00e32d0f46a24d72a1a906440a616965e2a742526dbd8abd2ff73c` | `f73a991e4b00e32d0f46a24d72a1a906440a616965e2a742526dbd8abd2ff73c` |
| `results/tables/phase2_numerical_selection_audit.csv` | `cf56bb2669bdd4370cb9923732a76009e3e60a7ada7324b30f10b35bbbd1a2fd` | `cf56bb2669bdd4370cb9923732a76009e3e60a7ada7324b30f10b35bbbd1a2fd` |
| `results/tables/phase2_paired_ablation_stats.csv` | `576dede3769d76af6b6393f76491d843c18009bd3b8cf1a8ec2c26291480ea38` | `576dede3769d76af6b6393f76491d843c18009bd3b8cf1a8ec2c26291480ea38` |
| `results/tables/phase2_pairwise_sparse_benchmark.csv` | `74bd5b19a5bebb87e4a8c47efc045fe803233741a21b80eb82edcc758c435554` | `74bd5b19a5bebb87e4a8c47efc045fe803233741a21b80eb82edcc758c435554` |

## Security and gas

- `MerkleQFVault.claim` rejects `address(0)` even for a valid Merkle leaf intentionally committed to a root. TypeScript manifest validation, Python manifest export, and the local demo bundle builder reject zero payout recipients. The native asset field remains the zero address by design.
- `npm run compile`: pass (`No contracts to compile`; patched contract was compiled before this final check).
- `npx tsc --noEmit`: pass.
- `npm test`: pass; 46/46 real round 27 claims, 142/142 real round 867 claims, plus reentrancy, rollback, deadlines, access control, replay, domain separation, and zero-recipient tests.
- `npm run benchmark`: six scales N=10, 50, 100, 250, 500, 1000; all N claim receipts on each vault. `scripts/summarize_gas.py` regenerated CSV, Markdown, EVM metadata, and 300 DPI Figure 4 from executed `receipt.gasUsed`.
- At N=1000, Merkle/naive publish: 137,465 / 69,611,868 gas; claim mean: 104,354 / 75,071 gas; full lifecycle: 104,491,413 / 144,682,972 gas. Across measured scales, publish savings 84.6%–99.8%, lifecycle savings 27.8%–70.4%.
- Patched Solidity SHA-256: `d075815a26fcac991a6a0ccb06cdd0bb65848ee36aa52a244c5abf94e1335af4`. Figure 4 SHA-256: `cac8ee5f352705323324913fe8dc5286252443a48d64e9e8d0de7c45fc9adac7`.
- Demo bundles remain byte compatible with the patched contract because their ABI schema and payouts did not change. Python independently reproduces both OpenZeppelin roots and verifies all 188 proofs. Bundle SHA-256: round 27 `5b6e090fe6cabdd84cdd6dfd3bdaa4190c03678d0ed41a154dd56be1db78ceb9`; round 867 `b458d44f5498e28829eb67d7b33baabda3215e59fdc5b3d2b95a666f76afc4bc`.

## Demo, package, and final gates

- Tab 03 keeps calculations lazy. Widget changes only compare normalized input/parameter signatures with the last computed signature, warn, disable root generation, and revoke a stale live bundle from Tab 04. Custom Table aggregates repeated donor/project contributions and resets to the ten-row sample. With no project supported by two donors, matching is zero and the full pool remains unallocated.
- Tab 03/04/05 mark local demo roots and frozen research evidence explicitly.
- `.venv\Scripts\python.exe -m pip check`: `No broken requirements found.`
- `.venv\Scripts\python.exe -m pytest -q`: `52 passed in 27.58s` on the final verification run.
- Redundant `.gitkeep` files were removed from populated project directories; `configs/dev/.gitkeep` remains because that directory is empty.
- `git check-ignore -v` confirms `data/raw/`, `data/processed/`, `.venv/`, `evm/node_modules/`, `evm/artifacts/`, `evm/cache/`, and `build/` are ignored; `git ls-files` lists no tracked file in those directories.
- This repository has no Git commit yet. Git `user.name` and `user.email` are unset. The owner should create the release commit and tag under their own identity.

```powershell
git config user.name "YOUR REAL NAME"
git config user.email "YOUR EMAIL"
git add -A
git commit -m "Release Phase 5.2 audited QF demo"
git tag -a phase5.2-final -m "Phase 5.2 submission"
```
