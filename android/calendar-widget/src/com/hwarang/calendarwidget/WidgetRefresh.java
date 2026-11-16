package com.hwarang.calendarwidget;

import android.app.job.JobParameters;
import android.app.job.JobService;
import java.time.YearMonth;

public final class WidgetRefresh extends JobService {
    @Override public boolean onStartJob(JobParameters params) {
        WidgetData.io.execute(() -> {
            WidgetData data = new WidgetData(this);
            YearMonth month = MonthWidget.shown(data);
            boolean team = data.prefs.getBoolean("team", false);
            String status = "";
            try {
                if (data.prefs.contains("session")) data.refresh(month, team);
            } catch (WidgetData.HttpFailure failure) {
                if (failure.code == 403 && team) {
                    data.setTeam(false);
                    data.prefs.edit().remove(data.cacheKey(month, true)).commit();
                    try { data.refresh(month, false); }
                    catch (WidgetData.HttpFailure fallback) {
                        if (fallback.code == 401 || fallback.code == 403) { data.clear(); status = fallback.code == 403 ? "권한 없음" : ""; }
                        else status = "갱신 지연 · 다시 시도해 주세요";
                    } catch (Exception fallback) { status = "갱신 지연 · 다시 시도해 주세요"; }
                } else if (failure.code == 401 || failure.code == 403) {
                    data.clear();
                    status = failure.code == 403 ? "권한 없음" : "";
                } else status = "갱신 지연 · 다시 시도해 주세요";
            } catch (Exception failure) {
                status = "갱신 지연 · 다시 시도해 주세요";
            } finally {
                data.prefs.edit().putString("state", status).apply();
                MonthWidget.paintAll(this);
                jobFinished(params, false);
            }
        });
        return true;
    }

    @Override public boolean onStopJob(JobParameters params) { return false; }
}
