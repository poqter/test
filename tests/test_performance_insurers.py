"""Preserve each campaign's payout for ambiguous names and term boundaries."""

import pandas as pd

from modules.performance.convention import compute_convention
from modules.performance.summer import compute_summer


def test_campaign_amounts_by_insurer_and_term():
    # Premium is already the collector's share. The summer campaign separately
    # normalizes a 25% share to 50%, whereas convention uses the uploaded amount.
    cases = [
        # Insurer, term, product, convention amount, summer amount
        ("한화생명", 10, "일반", 15_000, 20_000),
        ("한화손", 11, "일반", 30_000, 50_000),
        ("흥국화재", 10, "일반", 30_000, 20_000),
        (" kb손 ", 9, "치아", 30_000, 50_000),
        ("db손", 9, "일반", 30_000, 20_000),
        ("현대해상", 10, "일반", 20_000, 10_000),
        ("KB라이프", 9, "일반", 5_000, 10_000),
        ("DB생명", 10, "일반", 10_000, 10_000),
        ("흥국생명", 11, "일반", 10_000, 20_000),
        ("미분류", 11, "일반", 0, 0),
        (None, 11, "일반", 0, 0),
    ]
    contracts = pd.DataFrame(
        [(name, term, product) for name, term, product, _, _ in cases],
        columns=["보험사", "납입기간", "상품명"],
    ).assign(보험료=10_000, 쉐어율="25%", 계약일자="2026-07-01")

    convention = compute_convention(contracts)
    summer = compute_summer(contracts)
    assert convention["컨벤션환산금액"].tolist() == [case[3] for case in cases]
    assert summer["썸머환산금액"].tolist() == [case[4] for case in cases]
