"""Recompute paired inference solely from the persisted synthetic trial CSV."""
import sys
from pathlib import Path
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/"src"))
sys.path.insert(0, str(ROOT))
from qf_hybrid.experiments.reporting import write_table
from scripts.run_phase2_heldout import _paired_stats


def main():
    rows = pd.read_csv(ROOT/"results/tables/phase2_heldout_synthetic.csv").to_dict("records")
    stats = _paired_stats(rows)
    write_table(ROOT/"results/tables/phase2_paired_ablation_stats", stats,
                "Phase 2 paired comparisons", "First minus second on positive target gain/B; negative favors first. n_trial_pairs=30, n_seed_blocks=10; bootstrap and sign flips use seed-block means to respect shared backgrounds. Values below 1e-12 pool fraction are treated as numerical zero. Holm is applied separately to each comparison family.")
    print(f"Recomputed {len(stats)} paired comparisons from saved CSV")


if __name__ == "__main__":
    main()
