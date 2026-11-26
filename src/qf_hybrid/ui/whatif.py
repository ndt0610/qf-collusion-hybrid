"""Small editable donation worlds and in-memory demonstration payouts."""
from __future__ import annotations

import json
import re
from decimal import Decimal, ROUND_DOWN, ROUND_HALF_UP
from time import perf_counter

import pandas as pd

from qf_hybrid.experiments.trials import WorldCache
from qf_hybrid.ui.merkle_verify import _keccak, build_merkle_bundle
from qf_hybrid.ui.sandbox import frozen_config


def sample_donations() -> pd.DataFrame:
    return pd.DataFrame([
        {"Ví": donor, "Dự án": project, "Số tiền (USD)": amount}
        for donor, project, amount in (
            ("an", "Sách mở", 20), ("binh", "Sách mở", 15),
            ("chi", "Sách mở", 12), ("dung", "Sách mở", 9),
            ("an", "Nước sạch", 14), ("chi", "Nước sạch", 19),
            ("em", "Nước sạch", 21), ("binh", "Vườn chung", 10),
            ("dung", "Vườn chung", 18), ("em", "Vườn chung", 16),
        )
    ])


def parse_donations(frame: pd.DataFrame) -> dict:
    """Validate a bounded table and aggregate repeated donor/project rows in cents."""
    required = ("Ví", "Dự án", "Số tiền (USD)")
    if any(column not in frame for column in required):
        raise ValueError("Bảng cần ba cột: Ví, Dự án, Số tiền (USD)")
    if len(frame) > 200:
        raise ValueError("Demo giới hạn 200 dòng để phép tính đồ thị luôn nhanh")
    donations = {}
    for index, row in frame.iterrows():
        values = [row[column] for column in required]
        if all(pd.isna(value) or str(value).strip() == "" for value in values):
            continue
        if any(pd.isna(row[column]) or str(row[column]).strip() == "" for column in required[:2]):
            raise ValueError(f"Dòng {index+1}: cần điền Ví và Dự án")
        donor, project = (str(row[column]).strip() for column in required[:2])
        if not all(re.fullmatch(r"[\w .:-]{1,48}", value) for value in (donor, project)):
            raise ValueError(f"Dòng {index+1}: tên ví/dự án cần 1–48 ký tự chữ, số, khoảng trắng hoặc . : - _")
        try:
            money = Decimal(str(row[required[2]]))
        except Exception as error:
            raise ValueError(f"Dòng {index+1}: số tiền không hợp lệ") from error
        if not money.is_finite() or money <= 0 or money > 1_000_000:
            raise ValueError(f"Dòng {index+1}: số tiền phải dương và không quá 1.000.000 USD")
        money = money.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        if money <= 0:
            raise ValueError(f"Dòng {index+1}: số tiền nhỏ hơn 0,01 USD")
        key = donor, project
        donations[key] = donations.get(key, Decimal(0)) + money
    if not donations:
        raise ValueError("Bảng chưa có khoản đóng góp hợp lệ")
    if len({project for _, project in donations}) > 40:
        raise ValueError("Demo giới hạn 40 dự án")
    return donations


def run_custom_table(frame: pd.DataFrame, *, pool: int, beta: dict,
                     graph_key: tuple, tau: int) -> dict:
    started = perf_counter()
    donations = parse_donations(frame)
    projects = sorted({project for _, project in donations})
    if all(sum(project == p for _, p in donations) < 2 for project in projects):
        empty = {project: 0.0 for project in projects}
        return {"allocations": {key: empty.copy() for key in
                ("standard_qf", "pairwise_qf", "coqf_paper2025_alg2", "soft_base", "custom_soft")},
                "pool": pool, "seconds": perf_counter()-started,
                "donations": donations, "projects": projects,
                "unallocated": {key: pool for key in
                                ("standard_qf", "pairwise_qf", "coqf_paper2025_alg2", "soft_base", "custom_soft")}}
    selected = frozen_config()
    base_key = tuple(selected["soft_base"]["graph_key"])
    world = WorldCache(donations, keys=tuple(sorted({base_key, tuple(graph_key)})), seed=42)
    calculations = {
        "standard_qf": world.baseline("standard_qf", pool),
        "pairwise_qf": world.baseline("pairwise_qf", pool, tau=tau),
        "coqf_paper2025_alg2": world.baseline("coqf_paper2025_alg2", pool),
        "soft_base": world.soft(base_key, "soft_base", [selected["soft_base"]["beta"]], pool)[0],
        "custom_soft": world.soft(tuple(graph_key), "soft_full", [beta], pool)[0],
    }
    allocations = {mechanism: dict(zip(world.projects, map(float, values)))
                   for mechanism, values in calculations.items()}
    return {"allocations": allocations, "pool": pool, "seconds": perf_counter()-started,
            "donations": donations, "projects": world.projects,
            "unallocated": {key: max(0.0, pool-sum(values.values()))
                            for key, values in allocations.items()}}


def demo_bundle_from_allocation(allocations: dict[str, float], *, pool_usd: int,
                                source_label: str, mechanism_label: str) -> dict:
    """Map payout shares to a fixed local test pool; never imply USD/ETH exchange."""
    if not 0 < pool_usd <= 1_000_000_000:
        raise ValueError("Invalid research pool")
    projects = sorted(allocations)
    values = [Decimal(str(allocations[p])) for p in projects]
    if any(not value.is_finite() or value < 0 for value in values):
        raise ValueError("Invalid allocation")
    total = sum(values)
    if total <= 0:
        raise ValueError("Không có khoản chi dương để xây cây Merkle")
    unit_pool = 10**18
    target_paid = int((Decimal(unit_pool) * min(total / Decimal(pool_usd), Decimal(1))).to_integral_value(rounding=ROUND_DOWN))
    scaled = [Decimal(target_paid) * value / total for value in values]
    amounts = [int(value.to_integral_value(rounding=ROUND_DOWN)) for value in scaled]
    remainder = target_paid - sum(amounts)
    order = sorted(range(len(projects)), key=lambda i: (-(scaled[i] - amounts[i]), projects[i]))
    for i in order[:remainder]:
        amounts[i] += 1
    payouts = []
    project_map = {}
    for grant_id, (project, amount) in enumerate(zip(projects, amounts), 1):
        if amount <= 0:
            continue
        recipient = "0x" + _keccak(("qf-local-demo:" + project).encode("utf-8"))[-20:].hex()
        payouts.append({"grant_id": str(grant_id), "recipient": recipient,
                        "amount": str(amount)})
        project_map[str(grant_id)] = project
    canonical = json.dumps({"projects": projects, "amounts": amounts, "source": source_label,
                            "mechanism": mechanism_label}, sort_keys=True, ensure_ascii=False)
    round_id = str(9_000_000 + int.from_bytes(_keccak(canonical.encode("utf-8"))[:8], "big"))
    return build_merkle_bundle(payouts, round_id=round_id, pool_amount=unit_pool,
                               metadata={"source": source_label, "mechanism": mechanism_label,
                                         "project_map": project_map, "deployed_on_chain": False,
                                         "note": "Local 1 ETH test pool proportional to USD research allocation; no USD-to-ETH conversion"})
