"""Korean business dates for UI defaults and exports; storage timestamps stay UTC."""
from datetime import datetime
from zoneinfo import ZoneInfo

KST = ZoneInfo("Asia/Seoul")


def now_kst():
    return datetime.now(KST)


def today_kst(instant=None):
    if instant is None:
        return now_kst().date()
    if instant.tzinfo is None:
        raise ValueError("An explicit instant must include a timezone")
    return instant.astimezone(KST).date()
