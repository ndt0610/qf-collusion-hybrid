# Phase 3 handoff — hybrid Merkle vault

## Scope and result

Phase 3 implements the Python payout exporter, OpenZeppelin StandardMerkleTree bundle, Merkle vault, naive storage comparator, security tests and six-scale EVM gas benchmark. It uses the frozen Phase 2 `soft_base` configuration on real background rounds `42161:27` (46 grants) and `42161:867` (142 grants). Each round's research allocation is proportionally represented in a separate 100 ETH local native test pool; USD is never interpreted as wei. No Phase 4 `REPORT.md` was written.

## Reproduce

From the repository root on Windows with Python 3.12 and Node 24:

```powershell
python -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements.lock
.venv\Scripts\python.exe -m pip install --no-deps -e .
.venv\Scripts\python.exe -m pip check
.venv\Scripts\python.exe -m pytest -q
cd evm
npm ci
npm run compile
npm test
npm run benchmark
cd ..
.venv\Scripts\python.exe scripts\summarize_gas.py
```

The Gitcoin Parquet files are excluded from Git and must be retrieved first with `scripts/fetch_data.py`; the SHA-256 manifest in `data/manifests/sources.json` pins their bytes. The exporter requires the previously frozen `configs/heldout/frozen_mechanisms.json`. The Hardhat test deploys a fresh vault, then calls Python to bind the manifests to its address. The benchmark likewise deploys a fresh vault for each N and exports a manifest bound to that instance. Do not reuse a proof with another vault.

## Acceptance evidence

- `npm run compile`: Solidity 0.8.30, optimizer enabled with 200 runs, Cancun target, local chain 31337.
- `npm test`: complete Python → Merkle → EVM payouts on 46/46 and 142/142 grants; exact wei conservation. Negative tests cover modified amount, recipient, grant, round and proof byte; wrong vault and chain domain; replay; root immutability; ownership; claim/sweep deadlines; round isolation; reentrancy; recipient rejection; and naive payout, replay, deadline and sweep equivalence.
- `pytest -q`: 34 passed, including Phase 3 wei precision and frozen real manifest tests.
- `pip check`: no broken requirements.
- `npm run benchmark`: for N=10, 50, 100, 250, 500, 1000, records deployment, publication and **all** actual claim receipts for both vaults. Runtime was below 90 seconds, so no sampling or extrapolation was needed. The naive publisher sends batches of at most 100 grants (1, 1, 1, 3, 5, 10 transactions respectively), plus init and finalize.
- The canonical SHA-256 calculated independently by Python matches the Node bundle for all eight manifests. This check covers numeric project-map keys in both real rounds.

Validation log from the final local run:

```text
npm ci                 added 94 packages; pinned lockfile resolved
npm run compile        No contracts to compile (cached compiled Solidity 0.8.30 contracts)
npx tsc --noEmit       exit 0
npm test               PASS real round 27: 46/46; naive equivalent
                       PASS real round 867: 142/142
                       PASS reentrancy and failed transfers roll back state
                       PASS deadlines, permissions, sweep isolation, replay, domain separation
npm run benchmark      N=10,50,100,250,500,1000: all claims executed for both vaults
                       20.1 seconds for final benchmark run
pytest -q              34 passed in 20.96s
pip check              No broken requirements found
```

Gas evidence: `results/gas/phase3_gas_receipts.json` (raw receipts), `phase3_gas_benchmark.csv`, `phase3_gas_benchmark.md`, `phase3_evm_meta.json`, and `results/figures/fig04_gas_benchmark.png` (300 DPI). Each lifecycle value is publish gas plus actual claim receipts through 25%, 50%, or 100% of the grants; deploy gas is shown separately. The CSV includes min, median, mean and max per-claim gas. The publisher pays publish transactions, while claim gas is paid by whoever submits a permissionless claim; the committed recipient receives the native ETH.

Phase 5.2 remeasured gas after the vault added a zero-recipient claim guard. At N=1000, Merkle publish uses 137,465 gas and naive publish uses 69,611,868 gas (99.8% less). The Merkle claim mean is 104,354 gas versus 75,071 for naive, so Merkle shifts work to claimants. Full lifecycle gas is 104,491,413 versus 144,682,972 (27.8% less), excluding deploy. These numbers are local EVM gas units only. On-chain storage for publication is one Merkle root per round, while successful claims still add up to N `claimed` entries; Merkle proof verification grows with tree depth.

## Trust and limits

See `TRUST_MODEL.md`. The proof validates inclusion in an owner-published table, not the correctness of the off-chain science or payout selection. The manifest's provenance SHA-256 fields are released for review but are not checked by Solidity. Recipients in this test are deterministic demonstration addresses. Neither vault has been independently audited. The local EVM gas result is not a mainnet fee quote.

The pinned Node dependency tree has 12 `npm audit` findings (8 low, 4 high), all under development dependencies; `npm audit --omit=dev` reports zero. The high findings arise from the Hardhat dependency path to `zod`. Keep the pinned lockfile for reproduction and reassess advisories before any production deployment; this phase does not deploy to a public network.
