"""Summer campaign rules, parsing and data calculations.

Extracted from the existing implementation; public facade names are preserved.
"""
import pandas as pd
import numpy as np
import re

APP_VERSION = "1.1.0"

MONTHLY_TARGET = 500_000

MONTHLY_HANWHA_MIN_PREMIUM = 50_000

READY_BONUS_RATES = [0, 15, 20, 25, 30]

READY_BONUS_BY_COLLECTOR = {
    ("2025050036", "김원기"): 20,
    ("2024110242", "김종섭"): 20,
    ("2024060010", "도형진"): 20,
    ("2026050261", "이은애"): 20,
    ("2024050041", "강민희"): 15,
    ("2024050047", "강태구"): 15,
    ("2025060150", "김선우"): 15,
    ("2024060046", "김우람"): 15,
    ("2024060009", "김진우"): 15,
    ("2024050039", "모상우"): 15,
    ("2024050091", "박병선"): 15,
    ("2024050052", "송은솔"): 15,
    ("2025050268", "신현태"): 15,
    ("2024050036", "안계준"): 15,
    ("2024050040", "염준희"): 15,
    ("2025040304", "윤보연"): 15,
    ("2026010264", "이나경"): 15,
    ("2024050034", "이득재"): 15,
    ("2026070105", "이영민"): 15,
    ("2025110189", "조영은"): 15,
    ("2024050042", "최영님"): 15,
    ("2024060005", "최지희"): 15,
    ("2024050035", "현세영"): 15,
    ("2026010320", "홍민영"): 15,
}

SUMMER_GRADES = [
    ("HWARANG", 15_000_000),
    ("크라운", 10_000_000),
    ("트리플", 8_000_000),
    ("더블", 5_000_000),
    ("일반", 3_000_000),
]

TABLE_SEQ = 0

def mark(ok: bool) -> str:
    return "✅" if ok else "❌"

def won(x) -> str:
    try:
        return f"{float(x):,.0f} 원"
    except Exception:
        return ""

def signed_won(x) -> str:
    try:
        value = int(float(x))
        return f"{value:+,} 원" if value else "0 원"
    except Exception:
        return ""

def pct(x) -> str:
    try:
        return f"{float(x):,.0f} %"
    except Exception:
        return ""

def normalize_columns(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df.columns = [str(c).strip() for c in df.columns]
    return df

def standardize_columns(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()

    if "계약일" in df.columns and "계약일자" not in df.columns:
        df.rename(columns={"계약일": "계약일자"}, inplace=True)

    # 썸머 계산은 초회보험료가 아닌 계속보험료만 사용합니다.
    if "계속보험료" in df.columns:
        df["보험료"] = df["계속보험료"]

    return df

def parse_payment_period(series: pd.Series) -> pd.Series:
    """10, 10.0, '10년', '10 년납' 등을 숫자 10으로 정규화합니다."""
    text = series.astype("string").str.strip()
    text = text.str.replace(r"\s+", "", regex=True)
    text = text.str.replace(r"년납?$", "", regex=True)
    return pd.to_numeric(text, errors="coerce")

def normalize_collector_code(value) -> str:
    text = str(value).strip()
    return re.sub(r"\.0$", "", text)

def get_ready_bonus_rate(dfin: pd.DataFrame, selected_collector: str) -> tuple[int, str]:
    if selected_collector == "전체" or dfin is None or dfin.empty:
        return 0, "명단 미적용"

    identities = dfin.loc[
        dfin["수금자명"].astype(str) == str(selected_collector),
        ["수금자코드", "수금자명"],
    ].drop_duplicates()

    matched_rates = {
        READY_BONUS_BY_COLLECTOR.get(
            (normalize_collector_code(row["수금자코드"]), str(row["수금자명"]).strip())
        )
        for _, row in identities.iterrows()
    }
    matched_rates.discard(None)

    if len(matched_rates) == 1:
        return int(next(iter(matched_rates))), "회사 명단 기준 자동 선택"
    return 0, "회사 명단 미등록"

def safe_table_name(base: str) -> str:
    name = re.sub(r"[^A-Za-z0-9_]", "_", str(base))

    if not re.match(r"^[A-Za-z_]", name):
        name = f"tbl_{name}"

    return name[:254]

def safe_filename_part(text: str) -> str:
    """
    파일명에 사용할 수 없는 문자를 제거합니다.
    """
    text = str(text).strip()
    text = re.sub(r'[\\/:*?"<>|]', "_", text)
    text = re.sub(r"\s+", "_", text)
    return text if text else "미지정"

def unique_sheet_name(wb, base, limit=31):
    name = str(base)[:limit] if base else "Sheet"

    if name not in wb.sheetnames:
        return name

    i = 2
    while True:
        suffix = f"_{i}"
        trunc = limit - len(suffix)
        cand = f"{name[:trunc]}{suffix}"

        if cand not in wb.sheetnames:
            return cand

        i += 1

def autosize_columns_full(ws, padding=5):
    for column_cells in ws.columns:
        max_len = max(
            len(str(cell.value)) if cell.value is not None else 0
            for cell in column_cells
        )

        ws.column_dimensions[column_cells[0].column_letter].width = max_len + padding

def is_hanwha_life_series(ins: pd.Series) -> pd.Series:
    ins = ins.astype(str).str.strip()

    return (
        ins.str.contains("한화", na=False)
        & ins.str.contains("생명", na=False)
    )

def is_db_nonlife_series(ins: pd.Series) -> pd.Series:
    ins = ins.astype(str).str.strip()

    return (
        ins.str.contains("DB", case=False, na=False)
        & (
            ins.str.contains("손", na=False)
            | ins.str.contains("화재", na=False)
            | ins.str.contains("손해", na=False)
        )
    )

def is_kb_nonlife_series(ins: pd.Series) -> pd.Series:
    ins = ins.astype(str).str.strip()

    return (
        ins.str.contains("KB", case=False, na=False)
        & (
            ins.str.contains("손", na=False)
            | ins.str.contains("화재", na=False)
            | ins.str.contains("손해", na=False)
        )
    )

def is_hanwha_nonlife_series(ins: pd.Series) -> pd.Series:
    ins = ins.astype(str).str.strip()

    return (
        ins.str.contains("한화", na=False)
        & (
            ins.str.contains("손", na=False)
            | ins.str.contains("화재", na=False)
            | ins.str.contains("손해", na=False)
        )
        & ~is_hanwha_life_series(ins)
    )

def is_heungkuk_nonlife_series(ins: pd.Series) -> pd.Series:
    ins = ins.astype(str).str.strip()

    return (
        ins.str.contains("흥국", na=False)
        & (
            ins.str.contains("화재", na=False)
            | ins.str.contains("손", na=False)
            | ins.str.contains("손해", na=False)
        )
    )

def is_special_nonlife_series(ins: pd.Series) -> pd.Series:
    """
    썸머 우대 손해보험사:
    흥국화재, KB손해, 한화손해, DB손해
    """
    return (
        is_db_nonlife_series(ins)
        | is_kb_nonlife_series(ins)
        | is_hanwha_nonlife_series(ins)
        | is_heungkuk_nonlife_series(ins)
    )

def is_nonlife_series(ins: pd.Series) -> pd.Series:
    ins = ins.astype(str).str.strip()

    return (
        ins.str.contains("손해|손보|화재|해상", regex=True, na=False)
        | is_special_nonlife_series(ins)
    )

def is_life_series(ins: pd.Series) -> pd.Series:
    ins = ins.astype(str).str.strip()

    return (
        ins.str.contains("생명", na=False)
        | ins.str.contains("라이프", na=False)
    )

def is_other_life_series(ins: pd.Series) -> pd.Series:
    return is_life_series(ins) & ~is_hanwha_life_series(ins)

def load_df(uploaded_file) -> pd.DataFrame:
    from io import BytesIO
    from modules.shared.runtime_cache import cached, digest_bytes
    if not hasattr(uploaded_file, "getvalue"):
        return standardize_columns(normalize_columns(pd.read_excel(uploaded_file)))
    payload = uploaded_file.getvalue()
    def parse():
        return standardize_columns(normalize_columns(pd.read_excel(BytesIO(payload))))
    frame = cached("parse:summer:source", "summer-source-v1:" + digest_bytes(payload), parse)
    return frame.copy(deep=True)

def exclude_contracts(df: pd.DataFrame):
    """
    제외 조건:
    - 일시납
    - 연금성 / 저축성
    - 본인계약
    - 계약상태가 정상이 아닌 모든 계약
    """
    excluded_df = pd.DataFrame()

    needed = {"납입방법", "상품군1", "상품군2", "계약상태", "본인계약"}

    if needed.issubset(df.columns):
        tmp = df.copy()

        tmp["납입방법"] = tmp["납입방법"].astype(str).str.strip()
        tmp["상품군1"] = tmp["상품군1"].astype(str).str.strip()
        tmp["상품군2"] = tmp["상품군2"].astype(str).str.strip()
        tmp["계약상태"] = tmp["계약상태"].astype(str).str.strip()
        tmp["본인계약"] = tmp["본인계약"].astype("string").str.strip().str.lower()

        is_lumpsum = tmp["납입방법"].str.contains("일시납", na=False)
        is_savings = (
            tmp["상품군1"].str.contains("연금성|저축성", regex=True, na=False)
            | tmp["상품군2"].str.contains("연금성|저축성", regex=True, na=False)
        )
        is_self_contract = tmp["본인계약"].isin(["y", "on"])
        is_not_normal = tmp["계약상태"].ne("정상")

        is_excluded = is_lumpsum | is_savings | is_self_contract | is_not_normal

        excluded_df = tmp[is_excluded].copy()
        df_valid = tmp[~is_excluded].copy()

        return df_valid, excluded_df

    return df.copy(), excluded_df

def find_data_issues(df: pd.DataFrame, require_valid_date: bool = True):
    """환산 계산 보류 사유와 쉐어율 조건 확인 사유를 행별로 반환합니다."""
    blocking = pd.Series("", index=df.index, dtype="object")
    condition = pd.Series("", index=df.index, dtype="object")

    def add_issue(target, mask, message):
        mask = pd.Series(mask, index=df.index).fillna(False)
        target.loc[mask] = target.loc[mask].apply(
            lambda current: f"{current} / {message}" if current else message
        )

    def blank_mask(column):
        text = df[column].astype("string").str.strip().str.lower()
        return df[column].isna() | text.isin(["", "nan", "none", "<na>"])

    for column in ["수금자코드", "수금자명", "보험사", "납입방법", "상품군1", "상품군2", "계약상태", "본인계약"]:
        add_issue(blocking, blank_mask(column), f"{column} 누락")

    # 본인계약 공란은 일반계약으로 정상 처리합니다.
    self_text = df["본인계약"].astype("string").str.strip().str.lower()
    self_blank = df["본인계약"].isna() | self_text.isin(["", "nan", "none", "<na>"])
    blocking.loc[self_blank & blocking.str.contains("본인계약 누락", na=False)] = blocking.loc[
        self_blank & blocking.str.contains("본인계약 누락", na=False)
    ].str.replace(r"(^| / )본인계약 누락(?= / |$)", "", regex=True).str.strip(" /")
    known_self_values = self_blank | self_text.isin(["y", "on", "n", "0", "off", "false"])
    add_issue(blocking, ~known_self_values, "본인계약 여부 확인 필요")

    period = parse_payment_period(df["납입기간"])
    add_issue(blocking, period.isna() | (period <= 0), "납입기간 확인 필요")

    premium = pd.to_numeric(df["계속보험료"], errors="coerce")
    add_issue(blocking, premium.isna() | (premium <= 0), "계속보험료 확인 필요")

    if require_valid_date:
        dates = pd.to_datetime(df["계약일자"], errors="coerce")
        add_issue(blocking, dates.isna(), "계약일자 확인 필요")

    share_text = (
        df["쉐어율"].astype("string").str.replace("%", "", regex=False).str.strip()
    )
    share_numeric = pd.to_numeric(share_text, errors="coerce")
    # 공란은 별도 선택 없이 100% 단독계약으로 기본 적용합니다.
    add_issue(
        blocking,
        share_numeric.notna() & ((share_numeric <= 0) | (share_numeric > 100)),
        "쉐어율 확인 필요",
    )

    insurer = df["보험사"].astype(str).str.strip()
    classified = is_nonlife_series(insurer) | is_life_series(insurer)
    add_issue(blocking, ~classified, "보험사 분류 확인 필요")

    return blocking, condition, share_numeric

def build_review_display(review_df: pd.DataFrame) -> pd.DataFrame:
    columns = [
        "원본행", "수금자명", "계약일자", "보험사", "상품명",
        "납입기간", "계속보험료", "쉐어율", "확인사항", "반영상태",
    ]
    if review_df is None or review_df.empty:
        return pd.DataFrame(columns=columns)

    out = review_df.copy()
    out.rename(columns={"_원본행번호": "원본행"}, inplace=True)
    for column in columns:
        if column not in out.columns:
            out[column] = ""
    return out[columns]

def build_excluded_with_reason(exdf: pd.DataFrame) -> pd.DataFrame:
    base_cols = [
        "수금자명",
        "계약일자",
        "보험사",
        "상품명",
        "납입기간",
        "계속보험료",
        "납입방법",
        "계약상태",
        "본인계약",
        "제외사유",
    ]

    if exdf is None or exdf.empty:
        return pd.DataFrame(columns=base_cols)

    tmp = standardize_columns(exdf.copy())

    def reason_row(row):
        reasons = []

        if "일시납" in str(row.get("납입방법", "")):
            reasons.append("일시납")

        product_group = f"{row.get('상품군1', '')} {row.get('상품군2', '')}"
        if "연금성" in product_group or "저축성" in product_group:
            reasons.append("연금/저축성")

        self_contract = str(row.get("본인계약", "")).strip().lower()
        if self_contract in ["y", "on"]:
            reasons.append("본인계약")

        status = str(row.get("계약상태", "")).strip()
        if status != "정상":
            reasons.append(f"계약상태: {status if status else '미입력'}")

        return " / ".join(reasons) if reasons else "제외 조건 미상"

    tmp["제외사유"] = tmp.apply(reason_row, axis=1)

    for col in base_cols:
        if col not in tmp.columns:
            tmp[col] = ""

    tmp["계약일자"] = pd.to_datetime(tmp["계약일자"], errors="coerce").dt.strftime("%Y-%m-%d")

    tmp["납입기간"] = parse_payment_period(tmp["납입기간"]).apply(
        lambda x: f"{int(x)}년" if pd.notnull(x) else ""
    )

    tmp["계속보험료"] = pd.to_numeric(tmp["계속보험료"], errors="coerce").apply(
        lambda x: won(x) if pd.notnull(x) else ""
    )

    return tmp[base_cols]

def check_required_columns(df: pd.DataFrame):
    required_columns = {
        "수금자명",
        "수금자코드",
        "계약일자",
        "보험사",
        "상품명",
        "납입기간",
        "계속보험료",
        "쉐어율",
        "납입방법",
        "상품군1",
        "상품군2",
        "계약상태",
        "본인계약",
    }

    return required_columns - set(df.columns)

def compute_summer(df: pd.DataFrame) -> pd.DataFrame:
    df = standardize_columns(df.copy())

    df["계약일자_raw"] = pd.to_datetime(df["계약일자"], errors="coerce")
    df["계약월"] = df["계약일자_raw"].dt.month

    df["보험료"] = pd.to_numeric(df["보험료"], errors="coerce").fillna(0)
    df["납입기간_num"] = parse_payment_period(df["납입기간"]).fillna(0).astype(int)

    if "쉐어율" in df.columns:
        df["쉐어율"] = pd.to_numeric(
            df["쉐어율"]
            .astype("string")
            .str.replace("%", "", regex=False)
            .str.strip(),
            errors="coerce",
        )
    else:
        df["쉐어율"] = np.nan

    df["원본보험료"] = df["보험료"]

    # 쉐어율 공란은 별도 선택 없이 100% 단독계약으로 적용합니다.
    df["쉐어율미입력"] = df["쉐어율"].isna()
    if "_공란적용쉐어율" not in df.columns:
        df["_공란적용쉐어율"] = 100.0
    df["_공란적용쉐어율"] = pd.to_numeric(
        df["_공란적용쉐어율"], errors="coerce"
    ).fillna(100.0)
    df["원본계산쉐어율"] = np.where(
        df["쉐어율미입력"], df["_공란적용쉐어율"], df["쉐어율"]
    )
    df["원본계산쉐어율"] = pd.to_numeric(df["원본계산쉐어율"], errors="coerce")

    valid_share = df["원본계산쉐어율"].between(1, 100, inclusive="both")
    is_shared = valid_share & (df["원본계산쉐어율"] < 100)
    df["적용쉐어율"] = np.where(is_shared, 50.0, np.where(valid_share, 100.0, df["원본계산쉐어율"]))
    df["쉐어건수"] = np.where(is_shared, 0.5, np.where(valid_share, 1.0, 0.0))

    # 원본 계속보험료는 원래 쉐어율이 이미 반영된 FP 귀속금액입니다.
    # 모든 공동계약을 50%로 통일하고 최종 원 미만 금액은 반올림 없이 버립니다.
    df["전체보험료역산"] = np.where(
        is_shared,
        df["원본보험료"] * 100 / df["원본계산쉐어율"],
        df["원본보험료"],
    )
    adjusted = np.where(
        is_shared,
        df["원본보험료"] * 50 / df["원본계산쉐어율"],
        df["원본보험료"],
    )
    df["실적보험료"] = np.floor(adjusted).astype(float)
    df["조정차액"] = df["실적보험료"] - df["원본보험료"]

    ins = df["보험사"].astype(str).str.strip()
    term = df["납입기간_num"]

    is_hanwha_life = is_hanwha_life_series(ins)
    is_special_nonlife = is_special_nonlife_series(ins)
    is_nonlife = is_nonlife_series(ins)
    is_other_nonlife = is_nonlife & ~is_special_nonlife
    is_other_life = is_other_life_series(ins)

    product_name = df.get("상품명", pd.Series("", index=df.index)).fillna("").astype(str)
    product_group = df.get("상품군2", pd.Series("", index=df.index)).fillna("").astype(str)
    df["치아보험자동판정"] = product_name.str.contains("치아", na=False) | product_group.str.contains("치아", na=False)
    if "_치아보험예외적용" not in df.columns:
        df["_치아보험예외적용"] = df["치아보험자동판정"]
    df["치아보험예외적용"] = df["_치아보험예외적용"].fillna(False).astype(bool)
    long_term_rule = (term > 10) | df["치아보험예외적용"]

    # ✅ 썸머 환산율
    # 손해보험
    # - 10년납 초과: 흥국/한화/KB/DB 250%, 이외 손해/화재 100%
    # - 10년납 이하: 흥국/한화/KB/DB 100%, 이외 손해/화재 50%
    #
    # 생명보험
    # - 10년납 초과: 한화생명 150%, 이외 생명보험 100%
    # - 10년납 이하: 한화생명 100%, 이외 생명보험 50%
    df["썸머율"] = np.select(
        [
            is_special_nonlife & long_term_rule,
            is_special_nonlife & ~long_term_rule,
            is_other_nonlife & long_term_rule,
            is_other_nonlife & ~long_term_rule,
            is_hanwha_life & long_term_rule,
            is_hanwha_life & ~long_term_rule,
            is_other_life & long_term_rule,
            is_other_life & ~long_term_rule,
        ],
        [
            250,
            100,
            100,
            50,
            150,
            100,
            100,
            50,
        ],
        default=0,
    ).astype(int)

    df["썸머환산금액"] = df["실적보험료"] * df["썸머율"] / 100

    def application_label(row):
        labels = []
        if pd.isna(row["쉐어율"]):
            labels.append(f"쉐어율 공란 → {row['적용쉐어율']:.0f}% {'기본' if row['적용쉐어율'] == 100 else '수동'} 적용")
        elif row["쉐어율"] < 100:
            if row["쉐어율"] == 50:
                labels.append("쉐어 50% 적용")
            else:
                labels.append(f"쉐어 조정 적용 {row['쉐어율']:g}% → 50%")
        if row["치아보험예외적용"]:
            labels.append("치아보험 예외 적용")
        return " · ".join(labels)

    df["적용 구분"] = df.apply(application_label, axis=1)

    return df

def check_monthly_requirements(dfin: pd.DataFrame):
    """
    월별 조건:
    1. 전체 월 환산업적 50만원 이상
    2. 한화생명 월 환산업적 합계 5만원 이상
    3. 한화생명 인정 건수 합계 1건 이상
    """
    if dfin.empty:
        return {
            "환산금액": 0,
            "한화생명5만": False,
            "한화생명1건": False,
            "한화생명인정건수": 0,
            "환산50만": False,
            "월달성": False,
        }

    summer_sum = dfin["썸머환산금액"].sum()
    amount_ok = summer_sum >= MONTHLY_TARGET

    # 한화생명 계약의 썸머 환산업적을 월 단위로 합산하여
    # 합계가 5만원 이상인지 판정합니다.
    hanwha_mask = is_hanwha_life_series(dfin["보험사"])
    hanwha_summer_sum = pd.to_numeric(
        dfin.loc[hanwha_mask, "썸머환산금액"], errors="coerce"
    ).fillna(0).sum()
    hanwha_count = pd.to_numeric(
        dfin.loc[hanwha_mask, "쉐어건수"], errors="coerce"
    ).fillna(0).sum()
    hanwha_amount_ok = hanwha_summer_sum >= MONTHLY_HANWHA_MIN_PREMIUM
    hanwha_count_ok = hanwha_count >= 1

    total_ok = amount_ok and hanwha_amount_ok and hanwha_count_ok

    return {
        "환산금액": summer_sum,
        "한화생명5만": hanwha_amount_ok,
        "한화생명1건": hanwha_count_ok,
        "한화생명인정건수": hanwha_count,
        "환산50만": amount_ok,
        "월달성": total_ok,
    }

def get_summer_grade(total_amount: float):
    """
    7월 + 8월 합산 환산업적 기준 등급 산정.
    가장 높은 등급부터 체크.
    """
    if total_amount > 15_000_000:
        return "HWARANG", 15_000_000

    for grade, target in SUMMER_GRADES[1:]:
        if total_amount >= target:
            return grade, target

    return "미달성", 0

def get_next_grade_gap(total_amount: float):
    ascending = [
        ("일반", 3_000_000),
        ("더블", 5_000_000),
        ("트리플", 8_000_000),
        ("크라운", 10_000_000),
        ("HWARANG", 15_000_000),
    ]

    for grade, target in ascending:
        if grade == "HWARANG":
            if total_amount <= target:
                return grade, target, max(1, target - total_amount + 1)
        elif total_amount < target:
            return grade, target, target - total_amount

    return None, None, 0

def check_final_summer_requirements(
    july_df: pd.DataFrame,
    august_df: pd.DataFrame,
    ready_bonus_rate: float = 0,
):
    """
    1. 월별 필수조건은 보너스 전 금액 기준으로 판단
    2. 등급 판정은 레디포썸머 보너스 반영 후 금액 기준으로 판단
    """
    july_req = check_monthly_requirements(july_df)
    august_req = check_monthly_requirements(august_df)

    base_total_amount = july_req["환산금액"] + august_req["환산금액"]
    bonus_amount = base_total_amount * ready_bonus_rate / 100
    final_total_amount = base_total_amount + bonus_amount

    amount_grade, grade_target = get_summer_grade(final_total_amount)
    next_grade, next_target, next_gap = get_next_grade_gap(final_total_amount)

    monthly_all_ok = july_req["월달성"] and august_req["월달성"]

    # 금액 기준 등급과 최종 인정 등급을 분리
    if monthly_all_ok:
        final_grade = amount_grade
    else:
        final_grade = "필수조건 미충족"

    return {
        "7월": july_req,
        "8월": august_req,
        "기본합산환산금액": base_total_amount,
        "레디포썸머보너스율": ready_bonus_rate,
        "레디포썸머보너스금액": bonus_amount,
        "합산환산금액": final_total_amount,
        "월별필수조건": monthly_all_ok,
        "금액기준등급": amount_grade,
        "최종인정등급": final_grade,
        "달성기준금액": grade_target,
        "다음등급": next_grade,
        "다음등급기준": next_target,
        "다음등급부족금액": next_gap,
    }

def to_styled(dfin: pd.DataFrame) -> pd.DataFrame:
    df = dfin.copy()

    if df.empty:
        return pd.DataFrame(columns=[
            "계약월",
            "수금자명",
            "계약일자",
            "보험사",
            "상품명",
            "납입기간",
            "원본 계속보험료",
            "원본 쉐어율",
            "적용 쉐어율",
            "전체 보험료 역산",
            "실적보험료",
            "조정 차액",
            "인정 건수",
            "썸머율",
            "썸머환산금액",
            "적용 구분",
        ])

    df["계약일자"] = pd.to_datetime(df["계약일자"], errors="coerce").dt.strftime("%Y-%m-%d")

    df["납입기간"] = parse_payment_period(df["납입기간"]).apply(
        lambda x: f"{int(x)}년" if pd.notnull(x) else ""
    )

    df["원본보험료"] = df["원본보험료"].map(won)
    df["쉐어율"] = df["쉐어율"].apply(lambda x: pct(x) if pd.notnull(x) else "공란")
    df["적용쉐어율"] = df["적용쉐어율"].apply(lambda x: pct(x) if pd.notnull(x) else "확인 필요")
    df["전체보험료역산"] = np.floor(pd.to_numeric(df["전체보험료역산"], errors="coerce")).map(won)
    df["실적보험료"] = df["실적보험료"].map(won)
    df["조정차액"] = df["조정차액"].map(signed_won)
    df["쉐어건수"] = df["쉐어건수"].apply(lambda x: f"{x:g}건")
    df["썸머율"] = df["썸머율"].map(pct)
    df["썸머환산금액"] = df["썸머환산금액"].map(won)

    df.rename(columns={
        "원본보험료": "원본 계속보험료",
        "쉐어율": "원본 쉐어율",
        "적용쉐어율": "적용 쉐어율",
        "전체보험료역산": "전체 보험료 역산",
        "조정차액": "조정 차액",
        "쉐어건수": "인정 건수",
    }, inplace=True)

    cols = [
        "계약월",
        "수금자명",
        "계약일자",
        "보험사",
        "상품명",
        "납입기간",
        "원본 계속보험료",
        "원본 쉐어율",
        "적용 쉐어율",
        "전체 보험료 역산",
        "실적보험료",
        "조정 차액",
        "인정 건수",
        "썸머율",
        "썸머환산금액",
        "적용 구분",
    ]

    return df[[c for c in cols if c in df.columns]]

def style_detail_table(dfin: pd.DataFrame):
    display = to_styled(dfin)
    highlight_cols = {
        "원본 쉐어율", "적용 쉐어율", "전체 보험료 역산", "실적보험료",
        "조정 차액", "인정 건수", "썸머율", "적용 구분",
    }

    def color_row(row):
        label = str(row.get("적용 구분", ""))
        has_share = "쉐어" in label
        has_dental = "치아보험" in label
        color = ""
        if has_share and has_dental:
            color = "background-color: #eee3ff"
        elif has_dental:
            color = "background-color: #e3f2fd"
        elif has_share:
            color = "background-color: #fff4cc"
        return [color if col in highlight_cols else "" for col in row.index]

    try:
        return display.style.apply(color_row, axis=1)
    except ImportError:
        # 배포 환경에 스타일 선택 의존성이 없더라도 계산과 표 표시는 유지합니다.
        return display

def adjustment_summary(dfin: pd.DataFrame) -> dict:
    if dfin is None or dfin.empty:
        return {"원본": 0, "조정": 0, "차액": 0, "증가": 0, "감소": 0, "쉐어건수": 0}
    diff = pd.to_numeric(dfin["조정차액"], errors="coerce").fillna(0)
    return {
        "원본": dfin["원본보험료"].sum(),
        "조정": dfin["실적보험료"].sum(),
        "차액": diff.sum(),
        "증가": diff[diff > 0].sum(),
        "감소": diff[diff < 0].sum(),
        "쉐어건수": int((dfin["적용쉐어율"] < 100).sum()),
    }

def make_collector_summary(july_df: pd.DataFrame, august_df: pd.DataFrame) -> pd.DataFrame:
    """
    수금자별 요약은 기본 환산업적 기준으로 표시.
    레디포썸머 보너스는 수금자 선택 시 회사 명단 기준으로 자동 선택되며 수정할 수 있습니다.
    """
    all_df = pd.concat([july_df, august_df], ignore_index=True)

    rows = []

    if all_df.empty:
        return pd.DataFrame(columns=[
            "수금자명",
            "7월건수",
            "7월쉐어미입력",
            "7월환산",
            "7월한화5만",
            "7월한화1건",
            "7월50만",
            "7월달성",
            "8월건수",
            "8월쉐어미입력",
            "8월환산",
            "8월한화5만",
            "8월한화1건",
            "8월50만",
            "8월달성",
            "기본합산환산",
            "월별필수조건",
            "기본금액등급",
        ])

    for collector, sub in all_df.groupby("수금자명", dropna=False):
        july_sub = sub[sub["계약월"] == 7].copy()
        august_sub = sub[sub["계약월"] == 8].copy()

        result = check_final_summer_requirements(
            july_sub,
            august_sub,
            ready_bonus_rate=0,
        )

        rows.append({
            "수금자명": collector,
            "7월건수": july_sub["쉐어건수"].sum(min_count=1),
            "7월쉐어미입력": int(july_sub["쉐어율"].isna().sum()),
            "7월환산": result["7월"]["환산금액"],
            "7월한화5만": mark(result["7월"]["한화생명5만"]),
            "7월한화1건": mark(result["7월"]["한화생명1건"]),
            "7월50만": mark(result["7월"]["환산50만"]),
            "7월달성": mark(result["7월"]["월달성"]),
            "8월건수": august_sub["쉐어건수"].sum(min_count=1),
            "8월쉐어미입력": int(august_sub["쉐어율"].isna().sum()),
            "8월환산": result["8월"]["환산금액"],
            "8월한화5만": mark(result["8월"]["한화생명5만"]),
            "8월한화1건": mark(result["8월"]["한화생명1건"]),
            "8월50만": mark(result["8월"]["환산50만"]),
            "8월달성": mark(result["8월"]["월달성"]),
            "기본합산환산": result["기본합산환산금액"],
            "월별필수조건": mark(result["월별필수조건"]),
            "기본금액등급": result["금액기준등급"],
        })

    summary = pd.DataFrame(rows)
    return summary

def format_summary_for_display(summary: pd.DataFrame) -> pd.DataFrame:
    df = summary.copy()

    for month in ["7월", "8월"]:
        count_col = f"{month}건수"
        missing_col = f"{month}쉐어미입력"

        if count_col in df.columns:
            def format_count(row):
                value = row.get(count_col)
                missing = int(row.get(missing_col, 0) or 0)
                base = (
                    f"{float(value):.2f}".rstrip("0").rstrip(".")
                    if pd.notnull(value)
                    else "0"
                )
                return f"{base}건 (공란 기본 100% {missing}건)" if missing else f"{base}건"

            df[count_col] = df.apply(format_count, axis=1)

        if missing_col in df.columns:
            df.drop(columns=[missing_col], inplace=True)

    for col in ["7월환산", "8월환산", "기본합산환산"]:
        if col in df.columns:
            df[col] = df[col].map(won)

    return df

def filter_by_collector(df: pd.DataFrame, selected_collector: str) -> pd.DataFrame:
    if selected_collector == "전체":
        return df.copy()

    return df[df["수금자명"].astype(str) == selected_collector].copy()

def filter_excluded_by_collector(excluded_disp: pd.DataFrame, selected_collector: str) -> pd.DataFrame:
    """
    엑셀 다운로드 시 제외계약도 선택한 수금자 기준으로 필터링합니다.
    """
    if excluded_disp is None or excluded_disp.empty:
        return pd.DataFrame()

    if selected_collector == "전체":
        return excluded_disp.copy()

    if "수금자명" not in excluded_disp.columns:
        return pd.DataFrame()

    return excluded_disp[
        excluded_disp["수금자명"].astype(str) == str(selected_collector)
    ].copy()
