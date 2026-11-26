import hashlib
import json

import scripts.run_phase2_heldout as heldout
from qf_hybrid.experiments.generators import inject_attack, synthetic_background
from qf_hybrid.experiments.tuning import beta_grid, pareto_rows, select


def test_heldout_reads_only_frozen_config_not_dev_tables(tmp_path, monkeypatch):
    (tmp_path/"configs/heldout").mkdir(parents=True)
    (tmp_path/"docs").mkdir()
    (tmp_path/"data/manifests").mkdir(parents=True)
    (tmp_path/"docs/EXPERIMENT_PROTOCOL.md").write_text("locked")
    (tmp_path/"data/manifests/sources.json").write_text("{}")
    config = {"split": {"dev": "42161:27", "heldout": ["42161:865", "42161:867"],
                        "sensitivity": "42161:29"},
              "protocol_sha256": hashlib.sha256(b"locked").hexdigest(),
              "source_manifest_sha256": hashlib.sha256(b"{}").hexdigest(),
              "selected": {"0.05": {"soft_full": {"beta": {"shapley": 0.8}}}}}
    (tmp_path/"configs/heldout/frozen_mechanisms.json").write_text(json.dumps(config))
    monkeypatch.setattr(heldout, "ROOT", tmp_path)
    assert heldout._read_frozen() == config


def test_frozen_selection_uses_only_dev_rows():
    rows = [{"mechanism": "soft_full", "graph_key": ("G1", 10, 1.0),
             "beta": {"shapley": 0.8}, "dev_mech_damage": 0.03, "dev_attack_gain": 0.02},
            {"mechanism": "soft_full", "graph_key": ("G2", 40, 1.5),
             "beta": {"shapley": 1.2}, "dev_mech_damage": 0.06, "dev_attack_gain": 0.0}]
    assert select(rows, "soft_full", 0.05)["beta"]["shapley"] == 0.8
    assert len(beta_grid("soft_full")) == 540


def test_empirical_counterfactual_exact_project_totals():
    background = synthetic_background(0)
    for family in ("pure_split_m40", "ring_3proj", "decoy_camouflage", "cross_cluster_split"):
        trial = inject_attack(background, family, 1000, synthetic=False)
        assert sum(trial.attacker_single.values()) == sum(trial.attacker_attack.values())


def test_pareto_excludes_dominated_candidate():
    rows = [{"mechanism": "a", "dev_mech_damage": 0.0, "dev_attack_gain": 0.1},
            {"mechanism": "b", "dev_mech_damage": 0.02, "dev_attack_gain": 0.08},
            {"mechanism": "c", "dev_mech_damage": 0.03, "dev_attack_gain": 0.09}]
    assert [row["mechanism"] for row in pareto_rows(rows)] == ["a", "b"]
