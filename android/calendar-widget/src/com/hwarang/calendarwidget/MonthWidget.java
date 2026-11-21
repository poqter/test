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
import android.text.Spannable;
import android.text.SpannableStringBuilder;
import android.text.style.ForegroundColorSpan;
import android.widget.RemoteViews;
import java.time.LocalDate;
import java.time.YearMonth;
import java.time.ZoneId;
import java.util.LinkedHashMap;
import java.util.Map;
import java.util.LinkedHashSet;
import org.json.JSONArray;
import org.json.JSONObject;

public final class MonthWidget extends AppWidgetProvider {
    private static final ZoneId SEOUL = ZoneId.of("Asia/Seoul");
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
        context.getSystemService(JobScheduler.class).schedule(new JobInfo.Builder(81, new ComponentName(context, WidgetRefresh.class))
            .setRequiredNetworkType(JobInfo.NETWORK_TYPE_ANY).setOverrideDeadline(30000).build());
    }

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
            case "refresh": break;
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
        boolean personal;
        boolean leave;
        boolean common;
        final java.util.ArrayList<JSONObject> events=new java.util.ArrayList<>();
        final LinkedHashSet<String> kinds = new LinkedHashSet<>();
    }

    private static Map<String, DayMark> summarize(JSONArray rows, boolean includeDone) {
        Map<String, DayMark> result = new LinkedHashMap<>();
        if (rows == null) return result;
        for (int i = 0; i < rows.length(); i++) {
            JSONObject event = rows.optJSONObject(i);
            if (event == null) continue;
            DayMark mark = result.computeIfAbsent(event.optString("day"), unused -> new DayMark());
            mark.personal |= event.optBoolean("personal");
            if (!includeDone && event.optBoolean("done")) continue;

            mark.common |= event.optBoolean("common");
            String kind = event.optString("kind");
            if ("휴무".equals(kind)) mark.leave = true;
            else { mark.events.add(event); mark.count++; mark.kinds.add(kind); }
        }
        return result;
    }

    private static PendingIntent dateLink(Context context, LocalDate day, boolean team, int id) {
        Intent intent=new Intent(context,DayActivity.class).addFlags(Intent.FLAG_ACTIVITY_NEW_TASK | Intent.FLAG_ACTIVITY_CLEAR_TASK | Intent.FLAG_ACTIVITY_EXCLUDE_FROM_RECENTS).setData(Uri.parse("hwarang-widget://day/"+day+"/"+team))
            .putExtra("day",day.toString()).putExtra("team",team);
        return PendingIntent.getActivity(context, id, intent, PendingIntent.FLAG_IMMUTABLE | PendingIntent.FLAG_UPDATE_CURRENT);
    }

    private static RemoteViews row(Context context) { return new RemoteViews(context.getPackageName(), R.layout.widget_row); }

    private static RemoteViews cell(Context context, CharSequence label, int color) {
        RemoteViews cell = new RemoteViews(context.getPackageName(), R.layout.widget_cell);
        cell.setTextViewText(R.id.cell, label);
        cell.setTextColor(R.id.cell, color);
        return cell;
    }

    private static void paint(Context context, int id) {
        WidgetData data = new WidgetData(context);
        YearMonth month = shown(data);
        boolean connected = data.prefs.contains("session"), team = data.prefs.getBoolean("team", false);
        boolean sunday = data.prefs.getBoolean("sunday", false);
        String state = data.prefs.getString("state", "");
        JSONObject cache;
        try { cache = data.cachedMonth(month, team); }
        catch (Exception error) { cache = new JSONObject(); }
        Map<String, DayMark> marks = summarize(cache.optJSONArray("rows"), data.prefs.getBoolean("includeDone", true));
        RemoteViews view = new RemoteViews(context.getPackageName(), R.layout.month_widget);
        view.setTextViewText(R.id.heading, month.getYear() + "년 " + month.getMonthValue() + "월");
        view.setInt(R.id.mine,"setBackgroundResource",team?R.drawable.tab_idle:R.drawable.tab_active);
        view.setInt(R.id.branch,"setBackgroundResource",team?R.drawable.tab_active:R.drawable.tab_idle);
        view.setTextColor(R.id.mine, !team ? 0xffffffff : 0xff486174);
        view.setTextColor(R.id.branch, team ? 0xffffffff : 0xff486174);
        int[] actions = {R.id.prev, R.id.today, R.id.next, R.id.mine, R.id.branch, R.id.refresh};
        String[] names = {"prev", "today", "next", "mine", "branch", "refresh"};
        for (int i = 0; i < actions.length; i++) view.setOnClickPendingIntent(actions[i], action(context, names[i], id));
        view.setOnClickPendingIntent(R.id.web, PendingIntent.getActivity(context, id,
            new Intent(Intent.ACTION_VIEW,Uri.parse("https://hwarang-calendar.streamlit.app/calendar?view=mobile-calendar")), PendingIntent.FLAG_IMMUTABLE | PendingIntent.FLAG_UPDATE_CURRENT));
        view.setTextViewText(R.id.status, !connected ? ("권한 없음".equals(state) ? "일정 조회 권한을 확인해 주세요" : "화랑 월간 달력 앱에서 계정을 연결해 주세요")
            : !state.isEmpty() ? state : !cache.has("rows") ? "일정 확인 중" : marks.isEmpty() ? "표시할 일정 없음" : "");
        view.removeAllViews(R.id.grid);
        view.removeAllViews(R.id.weekdays);
        for (char weekday : (sunday ? "일월화수목금토" : "월화수목금토일").toCharArray())
            view.addView(R.id.weekdays, cell(context, String.valueOf(weekday), weekday=='일'?0xffad354a:weekday=='토'?0xff326a9c:0xff486174));

        AppWidgetManager manager = AppWidgetManager.getInstance(context);
        Bundle sizes = manager.getAppWidgetOptions(id);
        java.util.Set<String> emptyDays = new java.util.HashSet<>();
        JSONArray confirmed = cache.optJSONArray("empty_days");
        if (confirmed != null) for(int i=0;i<confirmed.length();i++) emptyDays.add(confirmed.optString(i));
        LocalDate today = LocalDate.now(SEOUL);
        LocalDate first = month.atDay(1);
        int offset = (first.getDayOfWeek().getValue() - (sunday ? 0 : 1) + 7) % 7;
        int weeks = (offset + month.lengthOfMonth() + 6) / 7;
        for (int week = 0; week < weeks; week++) {
            RemoteViews line = row(context);
            for (int col = 0; col < 7; col++) {
                LocalDate day = first.plusDays(week * 7 + col - offset);
                if (!YearMonth.from(day).equals(month)) {
                    line.addView(R.id.row, cell(context, "", 0xff486174));
                    continue;
                }
                DayMark mark = marks.get(day.toString());
                RemoteViews date=new RemoteViews(context.getPackageName(),R.layout.widget_date);
                int height=sizes.getInt(AppWidgetManager.OPTION_APPWIDGET_MIN_HEIGHT,270);
                int dayHeight=(height-100)/weeks;
                boolean leave=mark!=null && mark.leave;
                int total=mark==null?0:mark.events.size();
                int available=dayHeight-18-(leave?13:0);
                float fontScale=context.getResources().getConfiguration().fontScale;
                int textLine=(int)Math.ceil(14*fontScale);
                int limit=Math.min(2,Math.max(0,available/textLine));
                if(total>limit)limit=Math.min(limit,Math.max(0,(available-(int)Math.ceil(12*fontScale))/textLine));
                int titleLines=available-(total>limit?(int)Math.ceil(12*fontScale):0)>=2*textLine*Math.min(total,limit)?2:1;
                date.setTextViewText(R.id.number,String.valueOf(day.getDayOfMonth()));
                date.setTextColor(R.id.number,day.getDayOfWeek()==java.time.DayOfWeek.SUNDAY?0xffad354a:day.getDayOfWeek()==java.time.DayOfWeek.SATURDAY?0xff326a9c:0xff183449);
                if(today.equals(day)){
                    date.setInt(R.id.date_cell,"setBackgroundColor",0xffe4f3f1);
                    date.setInt(R.id.number,"setBackgroundColor",0xff007577);
                    date.setTextColor(R.id.number,0xffffffff);
                }
                int[] rows={R.id.first_row,R.id.second_row};
                int[] titles={R.id.first_title,R.id.second_title};
                int[] accents={R.id.first_accent,R.id.second_accent};
                if(mark!=null)mark.events.sort(java.util.Comparator.comparing(e->e.optString("start")));
                for(int n=0;n<Math.min(total,limit);n++){
                    JSONObject event=mark.events.get(n);
                    date.setViewVisibility(rows[n],android.view.View.VISIBLE);
                    date.setInt(titles[n],"setMaxLines",titleLines);
                    date.setTextViewText(titles[n],event.optString("title",event.optString("kind")));
                    int color=event.optBoolean("common")?0xff995815:DOTS.getOrDefault(event.optString("kind"),0xff367684);
                    date.setInt(accents[n],"setBackgroundColor",color);
                }
                if(leave || (total==0 && connected && !team && confirmed!=null)){
                    boolean confirmedEmpty=emptyDays.contains(day.toString());
                    date.setViewVisibility(R.id.day_state,android.view.View.VISIBLE);
                    date.setTextViewText(R.id.day_state,leave?"휴무":confirmedEmpty?"일정 없음":"미등록");
                    date.setTextColor(R.id.day_state,leave || confirmedEmpty?0xff486174:0xff687984);
                }
                if(total>limit){
                    date.setViewVisibility(R.id.total_link,android.view.View.VISIBLE);
                    date.setTextViewText(R.id.total_link,"전체 "+total+"건 ›");
                }
                date.setContentDescription(R.id.date_cell,day+" 일정 "+total+"건"+(leave?" 휴무":""));
                date.setOnClickPendingIntent(R.id.date_cell,dateLink(context,day,team,id));
                line.addView(R.id.row, date);
            }
            view.addView(R.id.grid, line);
        }
        manager.updateAppWidget(id, view);
    }
}
