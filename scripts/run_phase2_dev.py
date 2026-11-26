"""Tune exclusively on predeclared synthetic and empirical dev trials."""
import csv
import hashlib
import json
import sys
from pathlib import Path
from time import perf_counter

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/"src"))
from qf_hybrid.experiments.reporting import write_table
from qf_hybrid.experiments.tuning import pareto_rows, run_dev


def flat(row):
    key = row["graph_key"]
    beta = row["beta"]
    return {"mechanism": row["mechanism"], "delta_max": row.get("delta_max", ""),
            "graph_method": key[0] if key else "", "k": key[1] if key else "",
            "resolution": key[2] if key else "", "tau": beta.get("tau", ""),
            "beta0": beta.get("beta0", ""), "beta_coh": beta.get("coh", ""),
            "beta_conc": beta.get("conc", ""), "beta_S": beta.get("shapley", ""),
            "beta_C": beta.get("centrality", ""), "beta_size": beta.get("size", ""),
            "dev_mech_damage": row["dev_mech_damage"], "dev_attack_gain": row["dev_attack_gain"],
            "infeasible_at_delta": row.get("infeasible_at_delta", "")}


def main():
    started = perf_counter()
    rows, selected, frozen, runtime = run_dev(ROOT)
    tables = ROOT/"results/tables"
    write_table(tables/"phase2_dev_selection", [flat(x) for x in selected],
                "Phase 2 dev selections", "All configurations selected on dev only. Damage and gain are fractions of the fixed matching pool; multiply by 100 for percent. The 5 empirical seed labels have one deterministic world design per family and are not independent replicates.")
    with (tables/"phase2_dev_frontier.csv").open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(flat(rows[0])))
        writer.writeheader(); writer.writerows(flat(row) for row in rows)
    write_table(tables/"phase2_dev_pareto", pareto_rows([flat(row) for row in rows]),
                "Phase 2 dev Pareto frontier", "Global nondominated candidates across all nine mechanisms. Both dev damage and positive attack gain are minimized; values below 1e-12 pool fraction are treated as numerical ties. The separate phase2_dev_frontier.csv contains the full predeclared grid for plotting and audit.")
    with (tables/"phase2_dev_runtime.json").open("w", encoding="utf-8") as stream:
        json.dump(runtime, stream, indent=2)
    frozen["source_manifest_sha256"] = hashlib.sha256((ROOT/"data/manifests/sources.json").read_bytes()).hexdigest()
    frozen["protocol_sha256"] = hashlib.sha256((ROOT/"docs/EXPERIMENT_PROTOCOL.md").read_bytes()).hexdigest()
    frozen["dev_wall_seconds"] = perf_counter()-started
    target = ROOT/"configs/heldout/frozen_mechanisms.json"
    temporary = target.with_suffix(".json.partial")
    temporary.write_text(json.dumps(frozen, indent=2, sort_keys=True)+"\n", encoding="utf-8")
    temporary.replace(target)
    print(f"Frozen {len(selected)} selections in {target}; wall {frozen['dev_wall_seconds']:.1f}s", flush=True)


if __name__ == "__main__":
    main()
