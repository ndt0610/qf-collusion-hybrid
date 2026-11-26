"""Rebuild all figures from saved Phase 2 CSV tables only."""
from pathlib import Path
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
TABLES = ROOT/"results/tables"
FIGURES = ROOT/"results/figures"
METHODS = ["standard_qf", "pairwise_qf", "coqf_paper2025_alg2", "hard_cluster",
           "size_only", "soft_base", "soft_shapley", "soft_centrality", "soft_full"]
COLORS = dict(zip(METHODS, plt.cm.tab10(np.linspace(0, 1, len(METHODS)))))


def tradeoff():
    all_rows = pd.read_csv(TABLES/"phase2_dev_frontier.csv")
    pareto = pd.read_csv(TABLES/"phase2_dev_pareto.csv")
    selected = pd.read_csv(TABLES/"phase2_dev_selection.csv")
    selected = selected[selected.delta_max == 0.05]
    fig, ax = plt.subplots(figsize=(10, 7))
    for method in METHODS:
        subset = all_rows[all_rows.mechanism == method]
        if method in ("standard_qf", "coqf_paper2025_alg2"):
            subset = subset.head(1)
        ax.scatter(100*subset.dev_mech_damage, 100*subset.dev_attack_gain,
                   s=8 if len(subset) > 10 else 24, alpha=0.10 if len(subset) > 10 else 0.45,
                   color=COLORS[method], label=method)
    ax.plot(100*pareto.dev_mech_damage, 100*pareto.dev_attack_gain,
            color="black", linewidth=1.5, alpha=.7, label="global Pareto frontier")
    for _, row in selected.iterrows():
        ax.scatter(100*row.dev_mech_damage, 100*row.dev_attack_gain,
                   s=90, facecolors="none", edgecolors=COLORS[row.mechanism], linewidths=2)
    ax.axvline(5, color="black", linewidth=1, linestyle="--", label="5% policy threshold")
    ax.set(xlabel="Dev mechanism damage on known-valid projects (% pool)",
           ylabel="Dev positive attack gain (% pool)",
           title="Dev security–fairness tradeoff; open circles are frozen 5% selections")
    ax.grid(alpha=.2)
    ax.legend(ncol=3, fontsize=8, loc="upper right")
    fig.tight_layout()
    fig.savefig(FIGURES/"fig01_tradeoff_frontier_dev.png", dpi=300)
    plt.close(fig)


def synthetic():
    data = pd.read_csv(TABLES/"phase2_heldout_synthetic.csv")
    families = ["decoy_camouflage", "cross_cluster_split", "ring_4proj", "strongly_concentrated_organic"]
    fig, axes = plt.subplots(2, 2, figsize=(15, 10), sharex=False)
    for ax, family in zip(axes.flat, families):
        subset = data[data.family == family]
        column = "mech_damage_H" if family == "strongly_concentrated_organic" else "delta_A_pos_pct"
        means = subset.groupby("mechanism")[column].mean().reindex(METHODS)*100
        stds = subset.groupby("mechanism")[column].std().reindex(METHODS).fillna(0)*100
        y = np.arange(len(METHODS))
        ax.barh(y, means, xerr=stds, color=[COLORS[x] for x in METHODS], alpha=.8,
                error_kw={"elinewidth": .7, "capsize": 2})
        ax.set(yticks=y, yticklabels=METHODS, xlabel="% of fixed matching pool",
               title=family.replace("_", " "))
        ax.invert_yaxis(); ax.grid(axis="x", alpha=.2)
    fig.suptitle("Synthetic held-out: mean and seed SD; organic panel is attack-free damage")
    fig.tight_layout()
    fig.savefig(FIGURES/"fig02_heldout_synthetic_ablation.png", dpi=300)
    plt.close(fig)


def empirical():
    data = pd.read_csv(TABLES/"phase2_heldout_empirical.csv")
    families = ["pure_split_m40", "decoy_camouflage", "cross_cluster_split"]
    matrices = []
    for rid in (865, 867, 29):
        block = data[data.round_id == rid].pivot_table(index="mechanism", columns="family",
            values="delta_A_pos_pct", aggfunc="mean").reindex(index=METHODS, columns=families)
        matrices.append(100*block.to_numpy())
    vmax = max(np.nanmax(x) for x in matrices)
    fig, axes = plt.subplots(1, 3, figsize=(15, 7), sharey=True)
    for ax, rid, values in zip(axes, (865, 867, 29), matrices):
        image = ax.imshow(values, cmap="viridis", vmin=0, vmax=vmax, aspect="auto")
        ax.set(xticks=range(3), xticklabels=["pure split", "decoy", "cross cluster"],
               yticks=range(9), yticklabels=METHODS,
               title=f"42161:{rid}" + (" (sensitivity)" if rid == 29 else " (held-out)"))
        ax.tick_params(axis="x", rotation=35)
        for i in range(9):
            for j in range(3):
                ax.text(j, i, f"{values[i,j]:.2f}", ha="center", va="center", fontsize=7,
                        color="white" if values[i,j] < vmax*.55 else "black")
    fig.suptitle("Gitcoin background injections; seed labels repeat one deterministic design")
    fig.subplots_adjust(left=.17, right=.87, bottom=.18, top=.88, wspace=.12)
    color_axis = fig.add_axes([.895, .22, .015, .6])
    fig.colorbar(image, cax=color_axis, label="Positive attacker gain (% pool)")
    fig.savefig(FIGURES/"fig03_heldout_empirical_gitcoin.png", dpi=300)
    plt.close(fig)


def main():
    FIGURES.mkdir(parents=True, exist_ok=True)
    tradeoff(); synthetic(); empirical()
    print("Wrote three 300 DPI Phase 2 figures from CSV tables")


if __name__ == "__main__":
    main()
