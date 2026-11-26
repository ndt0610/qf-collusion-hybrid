from pathlib import Path
from decimal import Decimal
import pandas as pd

from qf_hybrid.data.rounds import load_round, sha256


def test_round_loader_filters_and_aggregates(tmp_path: Path):
    donations = pd.DataFrame([
        {"chain_id":"42161","round_id":"27","application_id":"1","project_id":"P","donor_address":"0xAa","amount_in_usd":"1.25","timestamp":"2024-01-02T00:00:00Z"},
        {"chain_id":"42161","round_id":"27","application_id":"1","project_id":"P","donor_address":"0xaa","amount_in_usd":"2.75","timestamp":"2024-01-03T00:00:00Z"},
        {"chain_id":"42161","round_id":"27","application_id":"1","project_id":"P","donor_address":"0xbb","amount_in_usd":"0","timestamp":"2024-01-03T00:00:00Z"},
        {"chain_id":"42161","round_id":"27","application_id":"2","project_id":"Q","donor_address":"0xcc","amount_in_usd":"4","timestamp":"2024-01-03T00:00:00Z"},
        {"chain_id":"42161","round_id":"27","application_id":"1","project_id":"P","donor_address":"0xdd","amount_in_usd":"5","timestamp":"2024-02-03T00:00:00Z"},
    ])
    apps = pd.DataFrame([{"chain_id":"42161","round_id":"27","id":"1","project_id":"P","status":"APPROVED"},
                         {"chain_id":"42161","round_id":"27","id":"2","project_id":"Q","status":"REJECTED"}])
    rounds = pd.DataFrame([{"chain_id":"42161","id":"27","donations_start_time":"2024-01-01T00:00:00Z","donations_end_time":"2024-01-31T23:59:59Z","total_donations_count":"5","unique_donors_count":"4","total_amount_donated_in_usd":"13"}])
    paths = {"donations.parquet":donations,"applications.parquet":apps,"rounds.parquet":rounds}
    hashes = {}
    for name, frame in paths.items():
        frame.to_parquet(tmp_path/name)
        hashes[name] = sha256(tmp_path/name)
    loaded = load_round(tmp_path,"42161","27",hashes)
    assert loaded.contributions == {("0xaa","p"):Decimal("4.00")}
    assert loaded.audit["rows_kept"] == 2
    assert loaded.audit["usd_nonpositive"] == 1
    assert loaded.audit["application_not_approved"] == 1
    assert loaded.audit["outside_window_or_invalid_time"] == 1
