"""Post-held-out numerical audit; never updates the frozen configuration."""
from pathlib import Path
import pandas as pd

from qf_hybrid.experiments.reporting import write_table

ROOT = Path(__file__).resolve().parents[1]


def main():
    grid = pd.read_csv(ROOT/"results/tables/phase2_dev_frontier.csv")
    frozen = pd.read_csv(ROOT/"results/tables/phase2_dev_selection.csv")
    rows = []
    for branch in ("soft_shapley", "soft_full"):
        selected = frozen[(frozen.mechanism == branch) & (frozen.delta_max == .05)].iloc[0]
        near_zero = grid[(grid.mechanism == branch) & (grid.dev_mech_damage <= .05) &
                         (grid.dev_attack_gain < 1e-12)]
        alternative = near_zero.sort_values(["dev_mech_damage", "graph_method", "k", "resolution"]).iloc[0]
        for status, item in (("pre_frozen", selected), ("lowest_damage_if_numeric_zero", alternative)):
            rows.append({"mechanism": branch, "status": status, "graph_method": item.graph_method,
                         "k": int(item.k), "resolution": item.resolution,
                         "beta0": item.beta0, "beta_coh": item.beta_coh,
                         "beta_conc": item.beta_conc, "beta_S": item.beta_S, "beta_C": item.beta_C,
                         "dev_mech_damage": item.dev_mech_damage,
                         "dev_attack_gain": item.dev_attack_gain,
                         "near_zero_candidate_count": len(near_zero)})
    write_table(ROOT/"results/tables/phase2_numerical_selection_audit", rows,
                "Post-held-out numerical selection audit", "Diagnostic only. A 1e-12 pool-fraction tolerance would treat the listed positive gains around 1e-19 as numerical zero, then favor smaller dev damage. The frozen configuration and all held-out results remain unchanged; no alternative was evaluated on held-out.")
    print("Wrote numerical audit without modifying the frozen selection")


if __name__ == "__main__":
    main()
