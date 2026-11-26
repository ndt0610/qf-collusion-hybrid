"""Five-tab smoke and meaningful local UI interactions."""
from collections import defaultdict
from decimal import Decimal
from pathlib import Path
import re

from streamlit.testing.v1 import AppTest

from qf_hybrid.ui.charts import sandbox_frontier
from qf_hybrid.ui.formatting import safe_evidence_markdown
from qf_hybrid.ui.merkle_verify import verify_merkle_proof_with_trace
from qf_hybrid.ui.sandbox import frozen_config, make_trial, run_sandbox
from qf_hybrid.ui.whatif import (demo_bundle_from_allocation, run_custom_table,
                                 sample_donations)


def test_sandbox_preserves_paired_project_totals():
    for family in ("pure_split", "decoy_camouflage", "cross_cluster_split", "ring_3proj"):
        trial = make_trial(family, budget=750, m=17, seed=137)
        totals = []
        for events in (trial.attacker_single, trial.attacker_attack):
            by_project = defaultdict(Decimal)
            for (_, project), amount in events.items():
                by_project[project] += amount
            totals.append(dict(by_project))
            assert sum(events.values()) == Decimal(750)
        assert totals[0] == totals[1]


def test_whatif_and_editable_table_are_fresh_calculations():
    base = frozen_config()["soft_base"]
    default = run_sandbox()
    original = next(row for row in default["rows"] if row["mechanism"] == "soft_base")
    custom = next(row for row in default["rows"] if row["mechanism"] == "custom_soft")
    assert custom["gain_pct"] == original["gain_pct"]
    assert custom["damage_pct"] == original["damage_pct"]
    varied = run_sandbox(pool=15_000, organic_wallets=70,
                         custom_beta={**base["beta"], "shapley": .8},
                         custom_tau=250)
    assert varied["pool"] == 15_000
    assert any(row["mechanism"] == "pairwise_custom" for row in varied["rows"])
    assert next(row for row in varied["rows"] if row["mechanism"] == "custom_soft")["gain_pct"] != custom["gain_pct"]
    assert all(trace.mode == "markers" for trace in sandbox_frontier(varied["rows"]).data)

    sample = sample_donations()
    result = run_custom_table(sample, pool=10_000, beta=base["beta"],
                              graph_key=tuple(base["graph_key"]), tau=500)
    changed = sample.copy()
    changed.loc[0, "Số tiền (USD)"] = 80
    second = run_custom_table(changed, pool=10_000, beta=base["beta"],
                              graph_key=tuple(base["graph_key"]), tau=500)
    assert result["allocations"]["standard_qf"] != second["allocations"]["standard_qf"]
    bundle = demo_bundle_from_allocation(result["allocations"]["custom_soft"],
                                         pool_usd=10_000, source_label="test",
                                         mechanism_label="custom")
    assert bundle["demo_metadata"]["deployed_on_chain"] is False
    assert all(verify_merkle_proof_with_trace(bundle, row["grant_id"])["valid"]
               for row in bundle["leaves"])
    assert sum(int(row["amount"]) for row in bundle["leaves"]) + int(bundle["unallocated_amount"]) == 10**18


def test_evidence_matrix_has_no_dead_local_links():
    root = Path(__file__).resolve().parents[2]
    source = (root / "docs/CLAIMS_EVIDENCE_LIMITS.md").read_text(encoding="utf-8")
    rendered = safe_evidence_markdown(source)
    assert not re.search(r"(?<!!)\[[^\]]+\]\((?!https?://)", rendered)
    assert "**Gas CSV**" in rendered
    assert safe_evidence_markdown("[Nguồn](https://example.org)") == "[Nguồn](https://example.org)"


def test_five_tabs_presets_and_merkle_tamper():
    app = AppTest.from_file(Path(__file__).resolve().parents[2] / "app.py", default_timeout=30).run()
    assert not app.exception
    labels = [tab.label for tab in app.tabs]
    assert len(labels) == 5
    for index, label in enumerate(labels):
        app.session_state["active_tab"] = label
        app.run()
        assert not app.exception, label
        assert app.tabs[index].children, label
    app.session_state["active_tab"] = labels[2]
    app.run()
    assert app.session_state["sandbox_params"]["family"] == "decoy_camouflage"
    app.button(key="preset_pure_split").click().run()
    assert not app.exception
    assert app.session_state["form_family"] == "pure_split"
    assert app.session_state["sandbox_params"]["family"] == "decoy_camouflage"
    assert app.button(key="build_redteam_merkle").disabled
    app.session_state["active_tab"] = labels[3]
    app.run()
    assert any("XÁC THỰC HỢP LỆ" in item.value for item in app.markdown)
    app.button(key="tamper_plus_one").click().run()
    assert not app.exception
    assert any("BỊ TỪ CHỐI" in item.value for item in app.markdown)
    app.button(key="tamper_restore").click().run()
    assert not app.exception
    assert any("XÁC THỰC HỢP LỆ" in item.value for item in app.markdown)


def test_custom_table_and_whatif_flow_into_live_merkle_tab():
    app = AppTest.from_file(Path(__file__).resolve().parents[2] / "app.py", default_timeout=30).run()
    app.session_state["active_tab"] = "03 · Red Team"
    app.run()
    app.number_input(key="whatif_pool").set_value(15_000).run()
    app.slider(key="whatif_shapley").set_value(.8).run()
    assert not app.exception
    app.radio(key="sandbox_mode").set_value("Bảng đóng góp của tôi").run()
    assert not app.exception
    assert app.session_state["custom_table_result"]["pool"] == 15_000
    app.button(key="build_custom_merkle").click().run()
    assert not app.exception
    assert app.session_state["live_bundle"]["demo_metadata"]["source"] == "Bảng đóng góp tự nhập"
    app.number_input(key="whatif_pool").set_value(16_000).run()
    assert not app.exception
    assert app.session_state["custom_table_result"]["pool"] == 15_000
    assert app.button(key="build_custom_merkle").disabled
    assert "live_bundle" not in app.session_state
    assert app.warning
    app.session_state["active_tab"] = "04 · Merkle & Gas"
    app.run()
    assert not app.exception and app.session_state["merkle_source"] == "27"
    app.session_state["active_tab"] = "03 · Red Team"
    app.run()
    app.button(key="custom_calculate").click().run()
    assert not app.exception
    assert app.session_state["custom_table_result"]["pool"] == 16_000
    assert "live_bundle" not in app.session_state
    app.button(key="build_custom_merkle").click().run()
    assert not app.exception
    app.session_state["active_tab"] = "04 · Merkle & Gas"
    app.run()
    assert not app.exception
    assert app.session_state["merkle_source"] == "live"
    assert any("XÁC THỰC HỢP LỆ" in item.value for item in app.markdown)
    app.button(key="tamper_plus_one").click().run()
    assert any("BỊ TỪ CHỐI" in item.value for item in app.markdown)
    app.session_state["active_tab"] = "03 · Red Team"
    app.run()
    app.radio(key="sandbox_mode").set_value("Kịch bản Red Team").run()
    assert app.button(key="build_redteam_merkle").disabled
    app.button(key="sandbox_calculate").click().run()
    app.button(key="build_redteam_merkle").click().run()
    assert not app.exception
    assert app.session_state["live_bundle"]["demo_metadata"]["source"].startswith("Red Team synthetic")


def test_editor_edits_additions_deletions_and_invalid_values_are_lazy():
    app = AppTest.from_file(Path(__file__).resolve().parents[2] / "app.py", default_timeout=30).run()
    app.session_state["active_tab"] = "03 · Red Team"
    app.run()
    app.radio(key="sandbox_mode").set_value("Bảng đóng góp của tôi").run()
    app.button(key="build_custom_merkle").click().run()
    editor = "custom_editor_0"
    original = app.session_state["custom_table_result"]["donations"][("an", "Sách mở")]
    app.session_state[editor] = {"edited_rows": {0: {"Số tiền (USD)": 80}},
                                 "added_rows": [], "deleted_rows": []}
    app.run()
    assert not app.exception
    assert app.button(key="build_custom_merkle").disabled
    assert "live_bundle" not in app.session_state
    assert app.session_state["custom_table_result"]["donations"][("an", "Sách mở")] == original
    app.session_state["active_tab"] = "04 · Merkle & Gas"
    app.run()
    app.session_state["active_tab"] = "03 · Red Team"
    app.run()
    assert app.button(key="build_custom_merkle").disabled
    app.button(key="custom_calculate").click().run()
    assert app.session_state["custom_table_result"]["donations"][("an", "Sách mở")] == Decimal(80)
    assert not app.button(key="build_custom_merkle").disabled
    app.session_state[editor] = {"edited_rows": {0: {"Số tiền (USD)": 80}},
                                 "added_rows": [{"Ví": "an", "Dự án": "Sách mở", "Số tiền (USD)": 5}],
                                 "deleted_rows": [1]}
    app.run()
    assert not app.exception and app.button(key="build_custom_merkle").disabled
    app.button(key="custom_calculate").click().run()
    assert app.session_state["custom_table_result"]["donations"][("an", "Sách mở")] == Decimal(85)
    assert ("binh", "Sách mở") not in app.session_state["custom_table_result"]["donations"]
    app.session_state[editor] = {"edited_rows": {0: {"Số tiền (USD)": -5}},
                                 "added_rows": [], "deleted_rows": []}
    app.run()
    assert not app.exception and app.button(key="build_custom_merkle").disabled
    app.button(key="custom_calculate").click().run()
    assert not app.exception and app.error
    app.session_state[editor] = {"edited_rows": {0: {"Số tiền (USD)": None}},
                                 "added_rows": [], "deleted_rows": []}
    app.run()
    app.button(key="custom_calculate").click().run()
    assert not app.exception and app.error
    app.session_state[editor] = {"edited_rows": {0: {"Ví": None}},
                                 "added_rows": [], "deleted_rows": []}
    app.run()
    app.button(key="custom_calculate").click().run()
    assert not app.exception and app.error
    app.button(key="custom_reset").click().run()
    assert not app.exception
    assert len(app.session_state["custom_table_sample"]) == 10


def test_single_donation_keeps_pool_unallocated_and_redteam_stays_lazy():
    base = frozen_config()["soft_base"]
    single = sample_donations().iloc[:1]
    result = run_custom_table(single, pool=10_000, beta=base["beta"],
                              graph_key=tuple(base["graph_key"]), tau=500)
    assert all(sum(values.values()) == 0 for values in result["allocations"].values())
    assert all(value == 10_000 for value in result["unallocated"].values())
    app = AppTest.from_file(Path(__file__).resolve().parents[2] / "app.py", default_timeout=30).run()
    app.session_state["active_tab"] = "03 · Red Team"
    app.run()
    app.radio(key="sandbox_mode").set_value("Bảng đóng góp của tôi").run()
    app.session_state["custom_editor_0"] = {"edited_rows": {}, "added_rows": [],
                                             "deleted_rows": list(range(1, 10))}
    app.run()
    app.button(key="custom_calculate").click().run()
    assert not app.exception
    assert app.session_state["custom_table_result"]["unallocated"]["standard_qf"] == 10_000
    assert app.button(key="build_custom_merkle").disabled
    app.radio(key="sandbox_mode").set_value("Kịch bản Red Team").run()
    before = app.session_state["sandbox_result"]
    app.selectbox(key="form_family").set_value("pure_split").run()
    assert app.session_state["sandbox_result"] is before
    assert app.button(key="build_redteam_merkle").disabled
    app.button(key="sandbox_calculate").click().run()
    assert app.session_state["sandbox_result"]["family"] == "pure_split"
    assert not app.button(key="build_redteam_merkle").disabled
