# Phase 3 EVM gas benchmark

All entries are executed `receipt.gasUsed` on Hardhat 3, chain 31337, Cancun, solc 0.8.30, optimizer 200. Deployment is separate from lifecycle. Naive batches contain at most 100 payouts. All claims were executed at every N; lifecycle uses the first `ceil(ratio × N)` actual claim receipts. Savings = `(Naive − Merkle) / Naive`; negative means Merkle costs more.

| N | Batches | Deploy M / S | Publish M / S | Publish saving | Claim mean M / S | Claim max M / S | Life 25% M / S (saving) | Life 50% M / S (saving) | Life 100% M / S (saving) | Merkle break-even claims |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 10 | 1 | 856,944 / 1,057,518 | 137,465 / 892,622 | +84.6% | 98,922 / 74,587 | 99,866 / 75,067 | 434,740 / 1,117,823 (+61.1%) | 633,711 / 1,267,957 (+50.0%) | 1,126,689 / 1,638,492 (+31.2%) | 0 |
| 50 | 1 | 856,944 / 1,057,518 | 137,453 / 3,655,578 | +96.2% | 101,050 / 74,971 | 101,388 / 75,067 | 1,452,860 / 4,631,449 (+68.6%) | 2,665,353 / 5,532,253 (+51.8%) | 5,189,945 / 7,404,128 (+29.9%) | 0 |
| 100 | 1 | 856,944 / 1,057,518 | 137,465 / 7,109,328 | +98.1% | 101,847 / 75,019 | 102,129 / 75,067 | 2,685,588 / 8,986,003 (+70.1%) | 5,234,538 / 10,862,678 (+51.8%) | 10,322,125 / 14,611,228 (+29.4%) | 0 |
| 250 | 3 | 856,944 / 1,057,518 | 137,465 / 17,543,622 | +99.2% | 102,834 / 75,048 | 102,910 / 75,067 | 6,617,602 / 22,272,843 (+70.3%) | 12,995,760 / 26,926,997 (+51.7%) | 25,845,913 / 36,305,572 (+28.8%) | 0 |
| 500 | 5 | 856,944 / 1,057,518 | 137,465 / 34,888,152 | +99.6% | 103,593 / 75,063 | 103,683 / 75,079 | 13,087,415 / 44,271,527 (+70.4%) | 26,036,622 / 53,654,902 (+51.5%) | 51,934,041 / 72,419,780 (+28.3%) | 0 |
| 1000 | 10 | 856,944 / 1,057,518 | 137,465 / 69,611,868 | +99.8% | 104,354 / 75,071 | 104,424 / 75,079 | 26,226,992 / 88,378,618 (+70.3%) | 52,316,824 / 107,148,296 (+51.2%) | 104,491,413 / 144,682,972 (+27.8%) | 0 |

M = MerkleQFVault; S = NaiveStorageQFVault. Full receipt distributions (min, median, mean, max), per-N raw receipts and 25/50/100% totals are in the CSV and `phase3_gas_receipts.json`.

Gas payer: the publisher pays deploy and publish transactions; the caller pays claim gas. The contract sends funds to the committed recipient even when a third party calls claim. The Merkle publisher also computes the tree off-chain. A single root uses O(1) storage per round, while successful claims populate up to O(N) `claimed` entries; each proof is O(log N).
