"""Deterministic filtering of the locked Grants Stack snapshot."""
from collections import defaultdict
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from pathlib import Path
import hashlib

import pandas as pd
import pyarrow.parquet as pq


@dataclass
class RoundData:
    chain_id: str
    round_id: str
    contributions: dict[tuple[str, str], Decimal]
    audit: dict


def sha256(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def verify_file(path: Path, expected: str) -> None:
    actual = sha256(path)
    if actual.lower() != expected.lower():
        raise ValueError(f"SHA-256 mismatch for {path.name}: {actual}")


def load_round(raw_dir: Path, chain_id: str, round_id: str, hashes: dict[str, str]) -> RoundData:
    for filename, digest in hashes.items():
        verify_file(raw_dir / filename, digest)
    filt = [("chain_id", "=", chain_id), ("round_id", "=", round_id)]
    donations = pq.read_table(raw_dir / "donations.parquet", filters=filt).to_pandas()
    applications = pq.read_table(raw_dir / "applications.parquet", filters=filt,
                                 columns=["id", "project_id", "status"]).to_pandas()
    rounds = pq.read_table(raw_dir / "rounds.parquet", filters=[("chain_id", "=", chain_id)]).to_pandas()
    selected = rounds[rounds.id.astype(str).str.lower() == round_id.lower()]
    if len(selected) != 1:
        raise ValueError("Expected exactly one round metadata row")
    info = selected.iloc[0]
    start = pd.to_datetime(info.donations_start_time, utc=True)
    end = pd.to_datetime(info.donations_end_time, utc=True)
    if pd.isna(start) or pd.isna(end) or end < start:
        raise ValueError("Missing or invalid donation window")
    if applications.id.str.lower().duplicated().any():
        raise ValueError("Duplicate application ID")
    app = {str(r.id).lower(): (str(r.project_id).lower(), r.status) for r in applications.itertuples()}
    raw_approved_join = sum(
        (entry := app.get(str(row.application_id).lower())) is not None
        and entry[1] == "APPROVED"
        and entry[0] == str(row.project_id).lower()
        for row in donations.itertuples(index=False)
    )
    counters = defaultdict(int)
    contributions = defaultdict(lambda: Decimal(0))
    donors = set()
    projects = set()
    for row in donations.itertuples(index=False):
        counters["rows_total"] += 1
        try:
            amount = Decimal(str(row.amount_in_usd))
        except InvalidOperation:
            counters["usd_unparseable"] += 1
            continue
        if not amount.is_finite() or amount <= 0:
            counters["usd_nonpositive"] += 1
            continue
        application = app.get(str(row.application_id).lower())
        if application is None:
            counters["application_missing"] += 1
            continue
        if application[1] != "APPROVED":
            counters["application_not_approved"] += 1
            continue
        if application[0] != str(row.project_id).lower():
            counters["project_id_mismatch"] += 1
            continue
        when = pd.to_datetime(row.timestamp, utc=True, errors="coerce")
        if pd.isna(when) or when < start or when > end:
            counters["outside_window_or_invalid_time"] += 1
            continue
        donor = str(row.donor_address).lower()
        project = str(row.project_id).lower()
        contributions[donor, project] += amount
        donors.add(donor)
        projects.add(project)
        counters["rows_kept"] += 1
    audit = dict(counters)
    audit.update({"chain_id": chain_id, "round_id": round_id,
                  "raw_approved_join_rows": raw_approved_join,
                  "raw_approved_join_ratio": raw_approved_join/len(donations) if len(donations) else 0.0,
                  "donors": len(donors), "projects": len(projects),
                  "donor_project_pairs": len(contributions),
                  "approved_application_count": sum(s == "APPROVED" for _, s in app.values()),
                  "application_count": len(app),
                  "usd_kept": str(sum(contributions.values(), Decimal(0))),
                  "metadata_donation_count": str(info.total_donations_count),
                  "metadata_donor_count": str(info.unique_donors_count),
                  "metadata_usd_total": str(info.total_amount_donated_in_usd),
                  "raw_rows_match_metadata": len(donations) == int(info.total_donations_count),
                  "raw_donors_match_metadata": donations.donor_address.str.lower().nunique() == int(info.unique_donors_count),
                  "raw_usd_matches_metadata": sum((Decimal(str(x)) for x in donations.amount_in_usd), Decimal(0)) == Decimal(str(info.total_amount_donated_in_usd)),
                  "window_start": str(start), "window_end": str(end)})
    return RoundData(chain_id, round_id, dict(contributions), audit)
