"""Read-only checks that the final manuscript agrees with frozen artifacts."""
import csv
import re
from pathlib import Path
from statistics import mean
from urllib.parse import unquote

from PIL import Image

ROOT = Path(__file__).resolve().parents[2]
REPORT = ROOT / "REPORT.md"
README = ROOT / "README.md"
MATRIX = ROOT / "docs/CLAIMS_EVIDENCE_LIMITS.md"


def csv_rows(relative):
    with (ROOT / relative).open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def test_deliverables_and_frozen_artifacts_exist():
    required = [REPORT, README, MATRIX,
                ROOT / "docs/MATH_SPEC.md", ROOT / "docs/DATA_CARD.md",
                ROOT / "docs/EXPERIMENT_PROTOCOL.md", ROOT / "docs/TRUST_MODEL.md",
                ROOT / "data/manifests/sources.json",
                ROOT / "results/tables/phase1_data_graph_profile.csv",
                ROOT / "results/tables/phase2_dev_selection.csv",
                ROOT / "results/tables/phase2_heldout_synthetic.csv",
                ROOT / "results/tables/phase2_heldout_empirical.csv",
                ROOT / "results/tables/phase2_paired_ablation_stats.csv",
                ROOT / "results/tables/phase2_paired_ablation_stats.md",
                ROOT / "results/tables/phase2_numerical_selection_audit.csv",
                ROOT / "results/gas/phase3_gas_benchmark.csv",
                ROOT / "results/gas/phase3_gas_receipts.json"]
    for path in required:
        assert path.is_file() and path.stat().st_size > 0, path
    for index in range(1, 5):
        matches = list((ROOT / "results/figures").glob(f"fig{index:02d}_*.png"))
        assert len(matches) == 1
        with Image.open(matches[0]) as figure:
            dpi = figure.info.get("dpi")
            assert dpi and min(dpi) >= 299, (matches[0], dpi)


def test_report_and_readme_relative_links_resolve():
    # All file, table and figure references in prose are Markdown links/images.
    pattern = re.compile(r"!?\[[^\]]+\]\(([^)]+)\)")
    for document in (REPORT, README, MATRIX):
        links = pattern.findall(document.read_text(encoding="utf-8"))
        assert links, document
        for target in links:
            if target.startswith(("https://", "http://", "mailto:", "#")):
                continue
            location = unquote(target.split("#", 1)[0])
            assert (document.parent / location).exists(), f"{document.name}: {target}"


def test_report_latex_delimiters_are_balanced():
    report = REPORT.read_text(encoding="utf-8")
    assert report.count(r"\[") == report.count(r"\]") >= 3
    assert all(line.count("$") % 2 == 0 for line in report.splitlines())


def report_mechanism_values(report, mechanism):
    for line in report.splitlines():
        cells = [cell.strip().replace("*", "").replace("`", "") for cell in line.split("|")]
        if len(cells) >= 5 and cells[1] == mechanism:
            return float(cells[2]), float(cells[3])
    raise AssertionError(f"Missing report row: {mechanism}")


def test_report_matches_heldout_and_inference():
    report = REPORT.read_text(encoding="utf-8")
    synthetic = csv_rows("results/tables/phase2_heldout_synthetic.csv")
    for mechanism in ("soft_base", "soft_shapley", "soft_full", "soft_centrality",
                      "coqf_paper2025_alg2", "hard_cluster"):
        attack = [float(r["delta_A_pos_pct"]) for r in synthetic
                  if r["mechanism"] == mechanism and r["family"] != "strongly_concentrated_organic"]
        organic = [float(r["mech_damage_H"]) for r in synthetic
                   if r["mechanism"] == mechanism and r["family"] == "strongly_concentrated_organic"]
        written_attack, written_damage = report_mechanism_values(report, mechanism)
        assert abs(written_attack - 100 * mean(attack)) < 0.00051
        assert abs(written_damage - 100 * mean(organic)) < 0.00051
    paired = csv_rows("results/tables/phase2_paired_ablation_stats.csv")
    comparison = next(r for r in paired if r["first"] == "soft_full" and r["second"] == "soft_base")
    assert f"+{100*float(comparison['mean_diff']):.3f}" in report
    assert f"{float(comparison['p_holm']):.7f}" in report
    assert "[+1.160,+1.389]" in report


def test_report_matches_gas_receipts_summary():
    report = REPORT.read_text(encoding="utf-8")
    rows = {int(r["n"]): r for r in csv_rows("results/gas/phase3_gas_benchmark.csv")}
    assert set(rows) == {10, 50, 100, 250, 500, 1000}
    for n, row in rows.items():
        line = next(line for line in report.splitlines() if line.startswith(f"| {n} |"))
        publish = f"{int(row['merkle_publish_gas']):,} / {int(row['naive_publish_gas']):,}"
        claim = f"{float(row['merkle_claim_mean']):,.0f} / {float(row['naive_claim_mean']):,.0f}"
        assert publish in line and claim in line
        for ratio in (25, 50, 100):
            assert f"{float(row[f'lifecycle_saving_{ratio}pct']):.1f}%" in line
    maximum, scale = max((float(row[f"lifecycle_saving_{ratio}pct"]), n)
                         for n, row in rows.items() for ratio in (25, 50, 100))
    assert 0 < maximum < 100
    assert f"{maximum:.1f}%" in next(line for line in report.splitlines()
                                  if line.startswith(f"| {scale} |"))
