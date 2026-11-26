import assert from "node:assert/strict";
import { execFileSync } from "node:child_process";
import { mkdirSync, readFileSync, writeFileSync } from "node:fs";
import { resolve } from "node:path";
import { performance } from "node:perf_hooks";
import { network } from "hardhat";
import { buildMerkle, type Manifest } from "./build_merkle.js";

const ROOT = resolve(process.cwd(), "..");
const MANIFESTS = resolve(ROOT, "results/runs/phase3/benchmark_manifests");
const GAS = resolve(ROOT, "results/gas");
const PYTHON = resolve(ROOT, ".venv/Scripts/python.exe");
const NS = [10, 50, 100, 250, 500, 1000];
const BATCH = 100;
const started = performance.now();
mkdirSync(MANIFESTS, { recursive: true });
mkdirSync(GAS, { recursive: true });
const { ethers } = await network.connect("local");
const Merkle = await ethers.getContractFactory("MerkleQFVault");
const Naive = await ethers.getContractFactory("NaiveStorageQFVault");
const rows: unknown[] = [];

function receiptGas(receipt: { gasUsed: bigint } | null): string {
  if (!receipt) throw new Error("Transaction receipt absent");
  return receipt.gasUsed.toString();
}

for (const n of NS) {
  const mVault = await Merkle.deploy();
  const mDeploy = receiptGas(await mVault.deploymentTransaction()!.wait());
  const sVault = await Naive.deploy();
  const sDeploy = receiptGas(await sVault.deploymentTransaction()!.wait());
  const vault = await mVault.getAddress();
  const roundDir = resolve(MANIFESTS, `n${n}`);
  mkdirSync(roundDir, { recursive: true });
  execFileSync(PYTHON, [resolve(ROOT, "scripts/export_phase3_manifests.py"),
    "--vault", vault, "--kind", "synthetic", "--synthetic-n", String(n), "--output", roundDir],
    { cwd: ROOT, stdio: "ignore" });
  const manifest = JSON.parse(readFileSync(resolve(roundDir, `synthetic_${n}.json`), "utf8")) as Manifest;
  assert.equal(manifest.payouts.length, n);
  const bundle = buildMerkle(manifest);
  writeFileSync(resolve(roundDir, `synthetic_${n}_bundle.json`), JSON.stringify(bundle, null, 2) + "\n");
  const round = BigInt(manifest.round_id);
  const deadline = Number((await ethers.provider.getBlock("latest"))!.timestamp) + 86400;
  const pool = BigInt(manifest.pool_amount);
  const mPublish = receiptGas(await (await mVault.publishRound(round, bundle.root, deadline, { value: pool })).wait());
  const sInit = receiptGas(await (await sVault.initRound(round, deadline, { value: pool })).wait());
  const batchGas: string[] = [];
  for (let i = 0; i < n; i += BATCH) {
    const batch = manifest.payouts.slice(i, i + BATCH);
    batchGas.push(receiptGas(await (await sVault.setPayoutsBatch(round,
      batch.map(p => BigInt(p.grant_id)), batch.map(p => p.recipient),
      batch.map(p => BigInt(p.amount)))).wait()));
  }
  const sFinal = receiptGas(await (await sVault.finalizeRound(round)).wait());

  // A dry run completed quickly enough to measure every claim at every scale.
  const sampleIndices = Array.from({ length: n }, (_, i) => i);
  assert.equal(new Set(sampleIndices).size, sampleIndices.length);
  const mClaim: string[] = [], sClaim: string[] = [];
  for (const index of sampleIndices) {
    const leaf = bundle.leaves[index];
    mClaim.push(receiptGas(await (await mVault.claim(round, leaf.grant_id,
      leaf.recipient, leaf.amount, leaf.proof)).wait()));
    sClaim.push(receiptGas(await (await sVault.claim(round, leaf.grant_id)).wait()));
  }
  rows.push({ n, round_id: manifest.round_id, vault_address: vault,
    manifest_canonical_sha256: bundle.manifest_canonical_sha256,
    sampling: "all",
    sampled_indices_zero_based: sampleIndices, batch_size: BATCH,
    merkle: { deploy_gas: mDeploy, publish_gas: mPublish, claim_gas_receipts: mClaim },
    naive: { deploy_gas: sDeploy, init_gas: sInit, batch_gas_receipts: batchGas,
      finalize_gas: sFinal, claim_gas_receipts: sClaim } });
  console.log(`N=${n}: ${sampleIndices.length} claim receipts each vault, ${batchGas.length} naive batches`);
}
const elapsed = (performance.now() - started) / 1000;
const raw = { meta: { chain_id: 31337, solc: "0.8.30", optimizer_enabled: true,
  optimizer_runs: 200, evm_version: "cancun", hardfork: "cancun",
  deployment_receipt_count: 12, benchmark_seconds: elapsed,
  generated_at_utc: new Date().toISOString(), batch_size: BATCH,
  note: "receipt.gasUsed only; deploy excluded from lifecycle" }, rows };
writeFileSync(resolve(GAS, "phase3_gas_receipts.json"), JSON.stringify(raw, null, 2) + "\n");
console.log(`Saved six-scale gas receipts in ${elapsed.toFixed(1)} s`);
