import assert from "node:assert/strict";
import { execFileSync } from "node:child_process";
import { mkdirSync, readFileSync, writeFileSync } from "node:fs";
import { resolve } from "node:path";
import { network } from "hardhat";
import { StandardMerkleTree } from "@openzeppelin/merkle-tree";
import { ZeroAddress, getAddress } from "ethers";
import { buildMerkle, LEAF_TYPES, validateManifest, type Manifest } from "../scripts/build_merkle.js";

const ROOT = resolve(process.cwd(), "..");
const PYTHON = resolve(ROOT, ".venv/Scripts/python.exe");
const OUT = resolve(ROOT, "results/runs/phase3/security_manifests");
const POOL = 100n * 10n ** 18n;

function exportReal(vault: string) {
  mkdirSync(OUT, { recursive: true });
  execFileSync(PYTHON, [resolve(ROOT, "scripts/export_phase3_manifests.py"), "--vault", vault,
    "--kind", "real", "--output", OUT], { cwd: ROOT, stdio: "inherit" });
  return [27, 867].map(id => JSON.parse(readFileSync(resolve(OUT, `real_${id}.json`), "utf8")) as Manifest);
}

async function rejects(action: () => Promise<unknown>, label: string) {
  let reverted = false;
  try { await action(); } catch { reverted = true; }
  assert.ok(reverted, `${label} must revert`);
}

const { ethers } = await network.connect("local");
const [owner, outsider] = await ethers.getSigners();
const Merkle = await ethers.getContractFactory("MerkleQFVault");
const Naive = await ethers.getContractFactory("NaiveStorageQFVault");
const merkle = await Merkle.deploy();
await merkle.waitForDeployment();
const naive = await Naive.deploy();
await naive.waitForDeployment();
const vaultAddress = await merkle.getAddress();
const [m27, m867] = exportReal(vaultAddress);
assert.equal(m27.payouts.length, 46);
assert.equal(m867.payouts.length, 142);
const b27 = buildMerkle(m27);
const b867 = buildMerkle(m867);
const pyCanonical = (id: number) => execFileSync(PYTHON, ["-c",
  "import json,hashlib,sys; m=json.load(open(sys.argv[1],encoding='utf-8')); print(hashlib.sha256(json.dumps(m,sort_keys=True,separators=(',',':'),ensure_ascii=False).encode()).hexdigest())",
  resolve(OUT, `real_${id}.json`)], { cwd: ROOT, encoding: "utf8" }).trim();
assert.equal(b27.manifest_canonical_sha256, pyCanonical(27));
assert.equal(b867.manifest_canonical_sha256, pyCanonical(867));
writeFileSync(resolve(OUT, "real_27_bundle.json"), JSON.stringify(b27, null, 2) + "\n");
writeFileSync(resolve(OUT, "real_867_bundle.json"), JSON.stringify(b867, null, 2) + "\n");
const mutated = (patch: Partial<Manifest>) => ({ ...m27, ...patch });
assert.throws(() => validateManifest(mutated({ pool_amount: "1" })), /payouts exceed pool/);
assert.throws(() => validateManifest(mutated({ payouts: [m27.payouts[0], m27.payouts[0]] })),
  /duplicate round\/grant/);
assert.throws(() => validateManifest(mutated({ round_id: (1n << 256n).toString() })), /overflow/);
assert.throws(() => validateManifest(mutated({ vault_address: ZeroAddress })), /zero vault/);
assert.throws(() => validateManifest(mutated({ payouts: [{ ...m27.payouts[0], recipient: ZeroAddress },
  ...m27.payouts.slice(1)] })), /zero recipient/);
assert.throws(() => validateManifest(mutated({ leaf_abi_types: ["uint256"] })), /ABI mismatch/);
const deadline = async () => Number((await ethers.provider.getBlock("latest"))!.timestamp) + 3600;

// Keep the second round open while the first is fully claimed.
await (await merkle.publishRound(27n, b27.root, await deadline(), { value: POOL })).wait();
await (await merkle.publishRound(867n, b867.root, await deadline(), { value: POOL })).wait();
await (await naive.initRound(27n, await deadline(), { value: POOL })).wait();
for (let i = 0; i < m27.payouts.length; i += 100) {
  const batch = m27.payouts.slice(i, i + 100);
  await (await naive.setPayoutsBatch(27n, batch.map(x => BigInt(x.grant_id)),
    batch.map(x => x.recipient), batch.map(x => BigInt(x.amount)))).wait();
}
await (await naive.finalizeRound(27n)).wait();

const first = b27.leaves[0];
const zeroRecipientTree = StandardMerkleTree.of(
  [["1", "31337", vaultAddress, ZeroAddress, "9301", "1", ZeroAddress, "1000"]], LEAF_TYPES);
await (await merkle.publishRound(9301n, zeroRecipientTree.root, await deadline(), { value: 1000n })).wait();
await assert.rejects(() => merkle.claim(9301n, 1n, ZeroAddress, 1000n,
  zeroRecipientTree.getProof(0)), /zero recipient/);
assert.equal((await merkle.rounds(9301n)).remaining, 1000n);
await rejects(() => (merkle.connect(outsider) as typeof merkle).publishRound(999n, b27.root, 9999999999n,
  { value: 1n }), "non-owner publish");
await rejects(async () => merkle.publishRound(27n, b27.root, await deadline(), { value: POOL }), "immutable root");
await rejects(() => merkle.claim(27n, first.grant_id, first.recipient,
  BigInt(first.amount) + 1n, first.proof), "amount tamper");
await rejects(() => merkle.claim(27n, first.grant_id, outsider.address,
  first.amount, first.proof), "recipient tamper");
await rejects(() => merkle.claim(27n, BigInt(first.grant_id) + 10000n,
  first.recipient, first.amount, first.proof), "grant tamper");
await rejects(() => merkle.claim(867n, first.grant_id,
  first.recipient, first.amount, first.proof), "round tamper");
const badProof = [...first.proof];
badProof[0] = "0x" + (badProof[0].slice(2, 4) === "aa" ? "bb" : "aa") + badProof[0].slice(4);
await rejects(() => merkle.claim(27n, first.grant_id, first.recipient,
  first.amount, badProof), "proof byte tamper");

// Correct roots from a different domain still fail at the actual vault.
const values = (m: Manifest, vault: string, chain: string, round: string) =>
  m.payouts.map(p => [m.schema_version, chain, vault, m.asset.address,
    round, p.grant_id, p.recipient, p.amount]);
for (const [id, vault, chain] of [[9001, outsider.address, "31337"], [9002, vaultAddress, "31338"]] as const) {
  const root = StandardMerkleTree.of(values(m27, vault, chain, String(id)), LEAF_TYPES).root;
  await (await merkle.publishRound(BigInt(id), root, await deadline(), { value: POOL })).wait();
  const proof = StandardMerkleTree.of(values(m27, vault, chain, String(id)), LEAF_TYPES).getProof(0);
  await rejects(() => merkle.claim(BigInt(id), m27.payouts[0].grant_id,
    m27.payouts[0].recipient, m27.payouts[0].amount, proof), `domain ${id}`);
}

for (const leaf of b27.leaves) {
  const recipientBefore = await ethers.provider.getBalance(leaf.recipient);
  await (await (merkle.connect(outsider) as typeof merkle).claim(27n, leaf.grant_id,
    leaf.recipient, leaf.amount, leaf.proof)).wait();
  await (await (naive.connect(outsider) as typeof naive).claim(27n, leaf.grant_id)).wait();
  assert.equal(await ethers.provider.getBalance(leaf.recipient) - recipientBefore,
    2n * BigInt(leaf.amount));
  assert.equal(await merkle.claimed(27n, leaf.grant_id), true);
  assert.equal(await naive.claimed(27n, leaf.grant_id), true);
}
assert.equal((await merkle.rounds(27n)).remaining, 0n);
assert.equal((await naive.rounds(27n)).remaining, 0n);
assert.equal((await merkle.rounds(867n)).remaining, POOL);
await rejects(() => merkle.claim(27n, first.grant_id, first.recipient,
  first.amount, first.proof), "merkle replay");
await rejects(() => naive.claim(27n, first.grant_id), "naive replay");
console.log("PASS real round 27: Python → Merkle → EVM, 46/46; naive equivalent");

for (const leaf of b867.leaves) {
  await (await (merkle.connect(outsider) as typeof merkle).claim(867n, leaf.grant_id,
    leaf.recipient, leaf.amount, leaf.proof)).wait();
}
assert.equal((await merkle.rounds(867n)).remaining, 0n);
console.log("PASS real round 867: Python → Merkle → EVM, 142/142");

// Isolated rounds for transfer failure and re-entry.
const Reentrant = await ethers.getContractFactory("ReentrantRecipient");
const Reject = await ethers.getContractFactory("RejectEtherRecipient");
const reentrant = await Reentrant.deploy(); await reentrant.waitForDeployment();
const reject = await Reject.deploy(); await reject.waitForDeployment();
for (const [rid, recipient] of [[9101, await reentrant.getAddress()],
  [9102, await reject.getAddress()]] as const) {
  const id = String(rid);
  const single: Manifest = { ...m27, round_id: id, pool_amount: "1000", unallocated_amount: "0",
    payouts: [{ grant_id: "1", recipient: getAddress(recipient), amount: "1000" }] };
  const b = buildMerkle(single);
  await (await merkle.publishRound(rid, b.root, await deadline(), { value: 1000n })).wait();
  if (rid === 9101) await (await reentrant.configure(vaultAddress, rid, 1n, 1000n, b.leaves[0].proof)).wait();
  await rejects(() => merkle.claim(rid, 1n, recipient, 1000n, b.leaves[0].proof),
    rid === 9101 ? "reentrancy" : "rejecting recipient");
  assert.equal(await merkle.claimed(rid, 1n), false);
  assert.equal((await merkle.rounds(rid)).remaining, 1000n);
}
console.log("PASS reentrancy and failed transfers roll back state");

// Two simultaneous rounds: sweep one, preserve the other.
const partial = { ...m27, round_id: "9201" };
const bp = buildMerkle(partial);
await (await merkle.publishRound(9201n, bp.root, await deadline(), { value: POOL })).wait();
const bsecond = buildMerkle({ ...m27, round_id: "9202" });
await (await merkle.publishRound(9202n, bsecond.root, (await deadline()) + 3600, { value: POOL })).wait();
await (await naive.initRound(9201n, await deadline(), { value: POOL })).wait();
await (await naive.setPayoutsBatch(9201n, m27.payouts.map(p => BigInt(p.grant_id)),
  m27.payouts.map(p => p.recipient), m27.payouts.map(p => BigInt(p.amount)))).wait();
await (await naive.finalizeRound(9201n)).wait();
const one = bp.leaves[0];
await (await merkle.claim(9201n, one.grant_id, one.recipient, one.amount, one.proof)).wait();
await (await naive.claim(9201n, one.grant_id)).wait();
await rejects(() => (merkle.connect(outsider) as typeof merkle).sweepUnclaimed(9201n, owner.address), "non-owner sweep");
await rejects(() => merkle.sweepUnclaimed(9201n, owner.address), "early merkle sweep");
await rejects(() => naive.sweepUnclaimed(9201n, owner.address), "early naive sweep");
await ethers.provider.send("evm_increaseTime", [3601]);
await ethers.provider.send("evm_mine", []);
await rejects(() => merkle.claim(9201n, bp.leaves[1].grant_id,
  bp.leaves[1].recipient, bp.leaves[1].amount, bp.leaves[1].proof), "late merkle claim");
await rejects(() => naive.claim(9201n, bp.leaves[1].grant_id), "late naive claim");
const expected = POOL - BigInt(one.amount);
assert.equal((await merkle.rounds(9201n)).remaining, expected);
assert.equal((await naive.rounds(9201n)).remaining, expected);
await (await merkle.sweepUnclaimed(9201n, owner.address)).wait();
await (await naive.sweepUnclaimed(9201n, owner.address)).wait();
assert.equal((await merkle.rounds(9201n)).remaining, 0n);
assert.equal((await naive.rounds(9201n)).remaining, 0n);
assert.equal((await merkle.rounds(9202n)).remaining, POOL);
const secondLeaf = bsecond.leaves[0];
await (await merkle.claim(9202n, secondLeaf.grant_id, secondLeaf.recipient,
  secondLeaf.amount, secondLeaf.proof)).wait();
assert.equal((await merkle.rounds(9202n)).remaining, POOL - BigInt(secondLeaf.amount));
console.log("PASS deadlines, permissions, sweep isolation, replay, domain separation");
