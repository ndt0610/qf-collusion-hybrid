"""Stable CSV and human-readable Markdown exports."""
import csv
import json
from pathlib import Path


def write_table(base: Path, rows, title, note=""):
    base.parent.mkdir(parents=True, exist_ok=True)
    rows = list(rows)
    if not rows:
        raise ValueError("No report rows")
    columns = list(rows[0])
    columns += sorted({key for row in rows for key in row}-set(columns))
    normalized = [{key: json.dumps(value, sort_keys=True) if isinstance(value, (dict, list, tuple)) else value
                   for key, value in row.items()} for row in rows]
    with base.with_suffix(".csv").open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=columns)
        writer.writeheader(); writer.writerows(normalized)
    lines = [f"# {title}", "", note, "", "| " + " | ".join(columns) + " |",
             "|" + "|".join("---" for _ in columns) + "|"]
    for row in normalized:
        lines.append("| " + " | ".join(str(row.get(key, "")) for key in columns) + " |")
    base.with_suffix(".md").write_text("\n".join(lines)+"\n", encoding="utf-8")
