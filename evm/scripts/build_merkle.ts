import { createHash } from "node:crypto";
import { readFile, writeFile } from "node:fs/promises";
import { getAddress, ZeroAddress } from "ethers";
import { StandardMerkleTree } from "@openzeppelin/merkle-tree";

export const LEAF_TYPES = ["uint256", "uint256", "address", "address", "uint256", "uint256", "address", "uint256"];
const MAX_UINT = (1n << 256n) - 1n;
const SHA256 = /^[0-9a-fA-F]{64}$/;

function uint(value: unknown, name: string): bigint {
  if (typeof value !== "string" || !/^(0|[1-9][0-9]*)$/.test(value)) throw new Error(`${name}: decimal string required`);
  const parsed = BigInt(value);
  if (parsed > MAX_UINT) throw new Error(`${name}: uint256 overflow`);
  return parsed;
}

function checksum(value: unknown, name: string): string {
  if (typeof value !== "string") throw new Error(`${name}: address required`);
  const normalized = getAddress(value);
  if (normalized !== value) throw new Error(`${name}: checksummed address required`);
  return normalized;
}

function canonicalJson(value: unknown): string {
  if (Array.isArray(value)) return `[${value.map(canonicalJson).join(",")}]`;
  if (value !== null && typeof value === "object") {
    const entries = Object.entries(value as Record<string, unknown>)
      .sort(([a], [b]) => a < b ? -1 : a > b ? 1 : 0);
    return `{${entries.map(([key, item]) => `${JSON.stringify(key)}:${canonicalJson(item)}`).join(",")}}`;
  }
  const encoded = JSON.stringify(value);
  if (encoded === undefined) throw new Error("Unsupported manifest value");
  return encoded;
}

export function canonicalSha256(value: unknown): string {
  return createHash("sha256").update(canonicalJson(value)).digest("hex");
}

export type Payout = { grant_id: string; recipient: string; amount: string };
export type Manifest = {
  schema_version: string; chain_id: string; vault_address: string; round_id: string;
  asset: { kind: string; address: string; decimals: number; unit: string; note: string };
  pool_amount: string; unallocated_amount: string; data_sha256: string;
  config_sha256: string; leaf_abi_types: string[]; payouts: Payout[];
  [key: string]: unknown;
};

export function validateManifest(value: unknown): Manifest {
  if (value === null || typeof value !== "object" || Array.isArray(value)) throw new Error("manifest object required");
  const m = value as Manifest;
  if (uint(m.schema_version, "schema_version") !== 1n) throw new Error("schema version");
  if (uint(m.chain_id, "chain_id") !== 31337n) throw new Error("local chain ID required");
  uint(m.round_id, "round_id");
  const vault = checksum(m.vault_address, "vault_address");
  if (vault === ZeroAddress) throw new Error("zero vault");
  if (!m.asset || m.asset.kind !== "native" || checksum(m.asset.address, "asset address") !== ZeroAddress ||
      m.asset.decimals !== 18 || m.asset.unit !== "wei" ||
      m.asset.note !== "Local EVM test pool proportional to research allocation; not a USD-to-ETH conversion") {
    throw new Error("invalid native asset metadata");
  }
  if (JSON.stringify(m.leaf_abi_types) !== JSON.stringify(LEAF_TYPES)) throw new Error("leaf ABI mismatch");
  if (!SHA256.test(m.data_sha256) || !SHA256.test(m.config_sha256)) throw new Error("invalid provenance SHA-256");
  const pool = uint(m.pool_amount, "pool_amount");
  const unallocated = uint(m.unallocated_amount, "unallocated_amount");
  if (pool === 0n || unallocated > pool) throw new Error("invalid pool");
  if (!Array.isArray(m.payouts) || m.payouts.length === 0) throw new Error("empty payouts");
  let total = 0n;
  const seen = new Set<string>();
  for (const row of m.payouts) {
    const id = uint(row.grant_id, "grant_id");
    const amount = uint(row.amount, "amount");
    if (checksum(row.recipient, "recipient") === ZeroAddress) throw new Error("zero recipient");
    if (amount === 0n) throw new Error("zero payout");
    const key = `${m.round_id}:${id}`;
    if (seen.has(key)) throw new Error("duplicate round/grant");
    seen.add(key);
    total += amount;
    if (total > pool) throw new Error("payouts exceed pool");
  }
  if (total + unallocated !== pool) throw new Error("pool conservation failure");
  return m;
}

export function buildMerkle(value: unknown) {
  const m = validateManifest(value);
  const values = m.payouts.map(row => [m.schema_version, m.chain_id, m.vault_address,
    m.asset.address, m.round_id, row.grant_id, row.recipient, row.amount]);
  const tree = StandardMerkleTree.of(values, LEAF_TYPES);
  tree.validate();
  for (const [index] of tree.entries()) {
    if (!tree.verify(index, tree.getProof(index))) throw new Error(`Invalid proof at index ${index}`);
  }
  const leaves = [...tree.entries()].map(([index, fields]) => ({
    grant_id: String(fields[5]), recipient: String(fields[6]), amount: String(fields[7]),
    proof: tree.getProof(index),
  })).sort((a, b) => BigInt(a.grant_id) < BigInt(b.grant_id) ? -1 : 1);
  return { root: tree.root, schema_version: m.schema_version, chain_id: m.chain_id,
    vault_address: m.vault_address, round_id: m.round_id, asset_address: m.asset.address,
    pool_amount: m.pool_amount, unallocated_amount: m.unallocated_amount,
    data_sha256: m.data_sha256, config_sha256: m.config_sha256,
    manifest_canonical_sha256: canonicalSha256(m), leaves };
}

export async function buildBundleFile(input: string, output: string) {
  const manifest = JSON.parse(await readFile(input, "utf8"));
  const bundle = buildMerkle(manifest);
  await writeFile(output, JSON.stringify(bundle, null, 2) + "\n", "utf8");
  return bundle;
}

if (process.env.PHASE3_MANIFEST && process.env.PHASE3_BUNDLE) {
  const result = await buildBundleFile(process.env.PHASE3_MANIFEST, process.env.PHASE3_BUNDLE);
  console.log(`Merkle root ${result.root}; ${result.leaves.length} leaves`);
}
