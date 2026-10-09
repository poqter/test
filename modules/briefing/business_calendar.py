"""Korean business days for observation; news still runs on holidays."""
from datetime import timedelta
import json
import os
import holidays


def calendar_rows(day):
    days=[day-timedelta(days=n) for n in range(40)]
    calendar=holidays.KR(years={d.year for d in days},language="ko")
    extra=set(json.loads(os.getenv("BRIEFING_EXTRA_HOLIDAYS_JSON","[]")))
    return [{"day":str(d),"is_business_day":d.weekday()<5 and d not in calendar and str(d) not in extra,
             "holiday_name":str(calendar.get(d) or ("임시휴일" if str(d) in extra else ""))} for d in days]


def is_business_day(day):
    return calendar_rows(day)[0]["is_business_day"]
