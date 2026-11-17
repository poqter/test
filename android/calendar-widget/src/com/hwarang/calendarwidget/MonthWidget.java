package com.hwarang.calendarwidget;

import android.app.PendingIntent;
import android.app.job.JobInfo;
import android.app.job.JobScheduler;
import android.appwidget.AppWidgetManager;
import android.appwidget.AppWidgetProvider;
import android.content.ComponentName;
import android.content.Context;
import android.content.Intent;
import android.net.Uri;
import android.os.Bundle;
import android.os.Build;
import android.util.SizeF;
import android.util.TypedValue;
import android.view.View;
import android.widget.RemoteViews;
import java.time.LocalDate;
import java.time.YearMonth;
import java.time.ZoneId;
import java.util.LinkedHashMap;
import java.util.Map;
import java.util.ArrayList;
import java.util.List;
import org.json.JSONArray;
import org.json.JSONObject;

public final class MonthWidget extends AppWidgetProvider {
    static final ZoneId SEOUL = ZoneId.of("Asia/Seoul");
    static final String REFRESH_FAILED = "갱신하지 못했어요 · 다시 시도";
    private static volatile long refreshingUntil;
    private static final String PREFIX = "com.hwarang.calendarwidget.";
    private static final Map<String, Integer> DOTS = new LinkedHashMap<>();
    static {
        DOTS.put("TA", 0xff137881); DOTS.put("AP", 0xff366fba); DOTS.put("PC", 0xffa04e88);
        DOTS.put("CS", 0xff587832); DOTS.put("청약", 0xffaf5b23); DOTS.put("기타", 0xff64748b);
    }

    static YearMonth currentMonth() { return YearMonth.now(SEOUL); }

    static YearMonth shown(WidgetData data) {
        String stored = data.prefs.getString("month", "");
        return stored.isEmpty() ? currentMonth() : YearMonth.parse(stored);
    }

    static int[] ids(Context context) {
        return AppWidgetManager.getInstance(context).getAppWidgetIds(new ComponentName(context, MonthWidget.class));
    }

    static void schedule(Context context) {
        if (ids(context).length == 0) return;
        int result = context.getSystemService(JobScheduler.class).schedule(new JobInfo.Builder(81, new ComponentName(context, WidgetRefresh.class))
            .setRequiredNetworkType(JobInfo.NETWORK_TYPE_ANY).setOverrideDeadline(30000).build());
        if (result != JobScheduler.RESULT_SUCCESS && refreshingUntil != 0) {
            new WidgetData(context).prefs.edit().putString("state", REFRESH_FAILED).apply();
            finishRefresh();
            paintAll(context);
        }
    }

    static void finishRefresh() { refreshingUntil = 0; }

    @Override public void onUpdate(Context context, AppWidgetManager manager, int[] ids) {
        for (int id : ids) paint(context, id);
        schedule(context);
    }

    @Override public void onAppWidgetOptionsChanged(Context context, AppWidgetManager manager, int id, Bundle options) {
        paint(context, id);
    }

    @Override public void onReceive(Context context, Intent intent) {
        super.onReceive(context, intent);
        String action = intent.getAction();
        if (action == null || !action.startsWith(PREFIX)) return;
        WidgetData data = new WidgetData(context);
        YearMonth month = shown(data);
        switch (action.substring(PREFIX.length())) {
            case "prev": if (!month.isAfter(currentMonth().minusYears(2))) return; month = month.minusMonths(1); break;
            case "next": if (!month.isBefore(currentMonth().plusYears(2))) return; month = month.plusMonths(1); break;
            case "today": month = currentMonth(); break;
            case "mine": data.setTeam(false); break;
            case "branch": if (data.prefs.contains("session")) data.setTeam(true); break;
            case "all": if (data.prefs.contains("session")) data.selectMember("", ""); break;
            case "refresh":
                if (android.os.SystemClock.elapsedRealtime() < refreshingUntil) return;
                WidgetStyle.allowRefresh(data.prefs);
                if (data.prefs.contains("session")) refreshingUntil = android.os.SystemClock.elapsedRealtime() + 60000;
                break;
            default: return;
        }
        data.prefs.edit().putString("month", month.equals(currentMonth()) ? "" : month.toString()).apply();
        paintAll(context);
        schedule(context);
    }

    private static PendingIntent action(Context context, String name, int id) {
        return PendingIntent.getBroadcast(context, id, new Intent(context, MonthWidget.class).setAction(PREFIX + name),
            PendingIntent.FLAG_IMMUTABLE | PendingIntent.FLAG_UPDATE_CURRENT);
    }

    static void paintAll(Context context) {
        for (int id : ids(context)) paint(context, id);
    }

    private static final class DayMark {
        int count;
        boolean leave;
        final List<JSONObject> events = new ArrayList<>();
    }

    private static Map<String, DayMark> summarize(JSONArray rows, boolean includeDone, JSONObject titles) {
        Map<String, DayMark> result = new LinkedHashMap<>();
        if (rows == null) return result;
        for (int i = 0; i < rows.length(); i++) {
            JSONObject event = rows.optJSONObject(i);
            if (event == null || (!includeDone && event.optBoolean("done"))) continue;
            DayMark mark = result.computeIfAbsent(event.optString("day"), unused -> new DayMark());
            mark.count++;
            String kind = event.optString("kind");
            if ("휴무".equals(kind)) mark.leave = true;
            try { event.put("display_title", titles.optString(Integer.toString(i))); }
            catch (org.json.JSONException impossible) { throw new IllegalStateException(impossible); }
            mark.events.add(event);
        }
        return result;
    }

    private static PendingIntent dateLink(Context context, LocalDate day, boolean team, int id, String member) {
        Intent intent = new Intent(context, DayAgendaActivity.class)
            .setData(Uri.fromParts("hwarang-widget", day + "/" + (team ? "branch" : "mine") + (member.isEmpty() ? "" : "/" + member), null))
            .addFlags(Intent.FLAG_ACTIVITY_NEW_TASK);
        return PendingIntent.getActivity(context, id, intent, PendingIntent.FLAG_IMMUTABLE);
    }

    static Intent calendarLink(LocalDate day, boolean team) {
        Uri link = Uri.parse("https://hwarang-calendar.streamlit.app/").buildUpon()
            .appendQueryParameter("view", "mobile-calendar").appendQueryParameter("widget_day", day.toString())
            .appendQueryParameter("widget_scope", team ? "branch" : "mine").build();
        return new Intent(Intent.ACTION_VIEW, link);
    }

    private static RemoteViews row(Context context) { return new RemoteViews(context.getPackageName(), R.layout.widget_row); }

    private static int dayColor(int weekday) {
        return weekday == 7 ? 0xffad414e : weekday == 6 ? 0xff316b9d : 0xff173446;
    }

    private static String activityLabel(String kind) {
        switch (kind) {
            case "TA": return "TA 연락";
            case "AP": return "AP 상담";
            case "PC": return "PC 미팅";
            case "CS": return "CS 관리";
            default: return kind;
        }
    }

    private static void entry(Context context, RemoteViews day, String label, int color, WidgetStyle wide) {
        RemoteViews item = new RemoteViews(context.getPackageName(), wide == null ? R.layout.widget_entry : R.layout.widget_entry_wide);
        if (wide != null) {
            item.setTextViewTextSize(R.id.entry, TypedValue.COMPLEX_UNIT_SP, wide.entrySp);
            int padding = Math.round(wide.paddingDp * context.getResources().getDisplayMetrics().density);
            item.setViewPadding(R.id.wide_entry_row, 0, padding, 0, padding);
        }
        item.setInt(R.id.stripe, "setBackgroundColor", color);
        item.setTextViewText(R.id.entry, label);
        day.addView(R.id.entries, item);
    }

    private static RemoteViews dayCell(Context context, LocalDate day, LocalDate today, DayMark mark,
                                        boolean team, int width, int height, int id, WidgetStyle wide, boolean titles, String member) {
        RemoteViews cell = new RemoteViews(context.getPackageName(), wide == null ? R.layout.widget_cell : R.layout.widget_cell_wide);
        if (day == null) return cell;
        if (wide != null) {
            cell.setTextViewTextSize(R.id.date_number, TypedValue.COMPLEX_UNIT_SP, wide.dateSp);
            cell.setTextViewTextSize(R.id.count, TypedValue.COMPLEX_UNIT_SP, wide.entrySp);
        }
        cell.setTextViewText(R.id.date_number, String.valueOf(day.getDayOfMonth()));
        boolean current = day.equals(today);
        cell.setTextColor(R.id.date_number, current ? 0xffffffff : dayColor(day.getDayOfWeek().getValue()));
        if (current) {
            cell.setInt(R.id.date_number, "setBackgroundResource", R.drawable.today_badge);
            cell.setInt(R.id.cell, "setBackgroundResource", R.drawable.today_cell);
        }
        if (mark != null) {
            boolean compact = width < 280 || height < 49;
            int availableLines = 0;
            if (wide != null) {
                int entryHeight = Math.max(16, estimatedTextHeight(context, wide.entrySp)) + 2 * wide.paddingDp;
                availableLines = Math.max(0, (height - 1 - estimatedTextHeight(context, wide.dateSp)
                    - (team ? estimatedTextHeight(context, wide.entrySp) : 0)) / entryHeight);
                compact = availableLines < (team ? 1 : 2);
            }
            if (titles && !team && wide == null && height >= 32) compact = false;
            if (compact || team) {
                cell.setTextViewText(R.id.count, (team ? "총 " : "") + mark.count + "건" + (!team && mark.leave ? " 휴무" : ""));
                cell.setViewVisibility(R.id.count, View.VISIBLE);
            }
            if (!compact && team) {
                Map<String, Integer> counts = new LinkedHashMap<>();
                for (JSONObject event : mark.events) counts.merge(event.optString("kind"), 1, Integer::sum);
                List<Map.Entry<String, Integer>> ranked = new ArrayList<>(counts.entrySet());
                ranked.sort((left, right) -> Integer.compare(right.getValue(), left.getValue()));
                int max = width >= 350 ? 2 : 1;
                List<String> labels = new ArrayList<>();
                int shown = 0;
                for (int i = 0; i < Math.min(max, ranked.size()); i++) {
                    Map.Entry<String, Integer> group = ranked.get(i);
                    shown += group.getValue();
                    labels.add(group.getKey() + " " + group.getValue());
                }
                String summary = String.join(" · ", labels);
                int remainder = mark.count - shown;
                String extra = "외 " + remainder + "건";
                boolean separate = false;
                if (remainder > 0) {
                    String full = summary + " · " + extra;
                    if (wide != null && availableLines >= 2) {
                        android.util.DisplayMetrics metrics = context.getResources().getDisplayMetrics();
                        android.graphics.Paint paint = new android.graphics.Paint();
                        paint.setTextSize(TypedValue.applyDimension(TypedValue.COMPLEX_UNIT_SP, wide.entrySp, metrics));
                        separate = paint.measureText(full) > ((width - 16) / 7f - 12) * metrics.density;
                    }
                    if (!separate) summary = full;
                }
                entry(context, cell, summary, 0xff73919e, wide);
                if (separate) entry(context, cell, extra, 0xff73919e, wide);
            } else if (!compact && !team) {
                mark.events.sort(java.util.Comparator.comparing(event -> {
                    String kind = event.optString("kind"), time = event.optString("time");
                    if ("휴무".equals(kind)) return "0";
                    if ("종일".equals(time)) return "1";
                    if (time.matches("[0-9]{2}:[0-9]{2}")) return "2" + time;
                    return "3";
                }));
                int limit = height >= 64 ? 2 : 1;
                if (titles && wide == null) {
                    int rows = Math.max(1, (height - 18) / 14);
                    limit = Math.min(2, rows);
                    if (mark.count > limit && rows == limit && rows > 1) limit--;
                }
                if (wide != null) {
                    limit = Math.min(wide.maxEntries, availableLines);
                    if (mark.count > limit && limit == availableLines) limit--;
                }
                for (int i = 0; i < Math.min(limit, mark.events.size()); i++) {
                    JSONObject event = mark.events.get(i);
                    String kind = event.optString("kind");
                    String label = activityLabel(kind);
                    String title = event.optString("display_title");
                    if (titles && !title.isEmpty()) label = title;
                    if (wide != null) {
                        String time = event.optString("time");
                        if (!time.isEmpty()) label = time + " · " + label;
                    }
                    entry(context, cell, label, DOTS.getOrDefault(kind, 0xff64748b), wide);
                }
                if (mark.count > limit && (!titles || wide != null || height >= 46))
                    entry(context, cell, "+" + (mark.count - limit) + "건", 0xffb0c0c8, wide);
            }
        }
        cell.setContentDescription(R.id.cell, day.toString() + (mark == null ? "" : " 일정 " + mark.count + "건")
            + (mark != null && mark.leave ? " 휴무" : "") + (current ? " 오늘" : ""));
        cell.setOnClickPendingIntent(R.id.cell, dateLink(context, day, team, id, member));
        return cell;
    }

    private static int estimatedTextHeight(Context context, int sp) {
        android.util.DisplayMetrics metrics = context.getResources().getDisplayMetrics();
        return (int) Math.ceil(TypedValue.applyDimension(TypedValue.COMPLEX_UNIT_SP, sp, metrics) * 1.45 / metrics.density);
    }

    private static void paint(Context context, int id) {
        WidgetData data = new WidgetData(context);
        AppWidgetManager manager = AppWidgetManager.getInstance(context);
        Bundle options = manager.getAppWidgetOptions(id);
        WidgetStyle style = WidgetStyle.read(data.prefs);
        RemoteViews rendered = null;
        if (Build.VERSION.SDK_INT >= 31) {
            ArrayList<SizeF> sizes = options.getParcelableArrayList(AppWidgetManager.OPTION_APPWIDGET_SIZES);
            if (sizes != null && !sizes.isEmpty() && sizes.size() <= 4) {
                Map<SizeF, RemoteViews> layouts = new LinkedHashMap<>();
                for (SizeF size : sizes) {
                    layouts.put(size, render(context, id, data, (int) size.getWidth(), (int) size.getHeight(), style));
                }
                rendered = new RemoteViews(layouts);
            }
        }
        if (rendered == null) {
            rendered = render(context, id, data, options.getInt(AppWidgetManager.OPTION_APPWIDGET_MIN_WIDTH, 300),
                options.getInt(AppWidgetManager.OPTION_APPWIDGET_MIN_HEIGHT, 270), style);
        }
        manager.updateAppWidget(id, rendered);
    }

    private static RemoteViews render(Context context, int id, WidgetData data, int width, int height, WidgetStyle style) {
        YearMonth month = shown(data);
        boolean connected = data.prefs.contains("session"), team = data.prefs.getBoolean("team", false);
        boolean sunday = data.prefs.getBoolean("sunday", false);
        String state = data.prefs.getString("state", "");
        String member = connected ? data.member(team) : "";
        boolean titles = connected && !team && data.showsTitles();
        JSONObject cache;
        try { cache = new JSONObject(data.prefs.getString(data.cacheKey(month, team), "{}")); }
        catch (org.json.JSONException error) { cache = new JSONObject(); }
        Map<String, DayMark> marks = summarize(connected ? cache.optJSONArray("rows") : null,
            data.prefs.getBoolean("includeDone", true), titles ? data.titles(month) : new JSONObject());
        String status = !connected ? ("권한 없음".equals(state) ? "일정 조회 권한을 확인해 주세요" : "설정에서 화랑 계정을 연결해 주세요")
            : android.os.SystemClock.elapsedRealtime() < refreshingUntil ? "갱신 중"
            : !state.isEmpty() ? state : !cache.has("rows") ? "일정 확인 중" : marks.isEmpty() ? "표시할 일정 없음" : "";
        LocalDate today = LocalDate.now(SEOUL);
        LocalDate first = month.atDay(1);
        int offset = (first.getDayOfWeek().getValue() - (sunday ? 0 : 1) + 7) % 7;
        int weeks = (offset + month.lengthOfMonth() + 6) / 7;
        int rowHeight = (height - 96 - (status.isEmpty() ? 0 : 16)) / weeks;
        WidgetStyle wide = width >= 520 && rowHeight >= 58 ? style : null;
        // The taller toolbar uses 40dp more than the compact toolbar.
        boolean wideToolbar = wide != null && rowHeight >= 58 + (40 + weeks - 1) / weeks;
        if (wideToolbar) rowHeight = (height - 136 - (status.isEmpty() ? 0 : 16)) / weeks;
        RemoteViews view = new RemoteViews(context.getPackageName(),
            wideToolbar ? R.layout.month_widget_wide : R.layout.month_widget);
        view.setTextViewText(R.id.heading, month.getYear() + "년 " + month.getMonthValue() + "월");
        view.setTextColor(R.id.mine, !team ? 0xffffffff : 0xff315364);
        view.setTextColor(R.id.branch, team ? 0xffffffff : 0xff315364);
        view.setInt(R.id.mine, "setBackgroundResource", !team ? R.drawable.active_scope : R.drawable.inactive_scope);
        view.setInt(R.id.branch, "setBackgroundResource", team ? R.drawable.active_scope : R.drawable.inactive_scope);
        int[] actions = {R.id.prev, R.id.today, R.id.next, R.id.mine, R.id.branch, R.id.refresh};
        String[] names = {"prev", "today", "next", "mine", "branch", "refresh"};
        for (int i = 0; i < actions.length; i++) view.setOnClickPendingIntent(actions[i], action(context, names[i], id));
        view.setOnClickPendingIntent(R.id.setup, PendingIntent.getActivity(context, id,
            new Intent(context, SetupActivity.class), PendingIntent.FLAG_IMMUTABLE | PendingIntent.FLAG_UPDATE_CURRENT));
        boolean search = connected && team;
        view.setViewVisibility(R.id.member_search, search ? View.VISIBLE : View.GONE);
        view.setViewVisibility(R.id.member_selected, search && !member.isEmpty() ? View.VISIBLE : View.GONE);
        view.setViewVisibility(R.id.member_all, search && !member.isEmpty() ? View.VISIBLE : View.GONE);
        view.setTextViewText(R.id.member_selected, data.memberLabel());
        PendingIntent picker = PendingIntent.getActivity(context, id,
            new Intent(context, MemberSearchActivity.class).addFlags(Intent.FLAG_ACTIVITY_NEW_TASK),
            PendingIntent.FLAG_IMMUTABLE | PendingIntent.FLAG_UPDATE_CURRENT);
        view.setOnClickPendingIntent(R.id.member_search, picker);
        view.setOnClickPendingIntent(R.id.member_selected, picker);
        view.setOnClickPendingIntent(R.id.member_all, action(context, "all", id));
        view.setTextViewText(R.id.status, status);
        if (REFRESH_FAILED.equals(status)) view.setOnClickPendingIntent(R.id.status, action(context, "refresh", id));
        view.setViewVisibility(R.id.status, status.isEmpty() ? View.GONE : View.VISIBLE);
        view.removeAllViews(R.id.grid);
        view.removeAllViews(R.id.weekdays);
        String days = sunday ? "일월화수목금토" : "월화수목금토일";
        for (int i = 0; i < days.length(); i++) {
            RemoteViews weekday = new RemoteViews(context.getPackageName(), R.layout.widget_weekday);
            weekday.setTextViewText(R.id.weekday, String.valueOf(days.charAt(i)));
            weekday.setTextColor(R.id.weekday, dayColor((i + (sunday ? 6 : 0)) % 7 + 1));
            view.addView(R.id.weekdays, weekday);
        }
        for (int week = 0; week < weeks; week++) {
            RemoteViews line = row(context);
            for (int col = 0; col < 7; col++) {
                LocalDate day = first.plusDays(week * 7 + col - offset);
                if (!YearMonth.from(day).equals(month)) day = null;
                line.addView(R.id.row, dayCell(context, day, today, day == null ? null : marks.get(day.toString()),
                    team, width, rowHeight, id, wide, titles, member));
            }
            view.addView(R.id.grid, line);
        }
        return view;
    }
}
