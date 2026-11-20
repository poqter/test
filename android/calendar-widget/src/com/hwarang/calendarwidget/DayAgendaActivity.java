package com.hwarang.calendarwidget;

import android.app.Activity;
import android.content.res.ColorStateList;
import android.graphics.drawable.GradientDrawable;
import android.graphics.drawable.RippleDrawable;
import android.content.ActivityNotFoundException;
import android.content.Intent;
import android.os.Bundle;
import android.view.View;
import android.widget.Button;
import android.widget.LinearLayout;
import android.widget.ScrollView;
import android.widget.TextView;
import android.widget.Toast;
import java.time.DateTimeException;
import java.time.LocalDate;
import java.time.format.DateTimeFormatter;
import java.util.ArrayList;
import java.util.Comparator;
import java.util.HashMap;
import java.util.List;
import java.util.Locale;
import java.util.Map;
import org.json.JSONArray;
import org.json.JSONObject;

public final class DayAgendaActivity extends Activity {
    private static final DateTimeFormatter DATE = DateTimeFormatter.ofPattern("M월 d일 (E)", Locale.KOREAN);
    private LocalDate day;
    private boolean team;
    private String member = "";
    private volatile int requestId;
    private TextView heading;
    private TextView scope;
    private LinearLayout modes;
    private Button timeOrder;
    private Button memberOrder;
    private int listHeight;
    private boolean grouped;
    private Boolean mayGroup;
    private JSONObject dayPayload;
    private boolean includeDone;
    private LinearLayout agendaRoot;
    private WidgetEventEditor editor;
    private Button add;
    private ScrollView scroll;
    private LinearLayout items;

    @Override public void onCreate(Bundle state) {
        super.onCreate(state);
        setFinishOnTouchOutside(true);
        if (!readDate(getIntent())) { finish(); return; }
        if (state != null) {
            day = LocalDate.parse(state.getString("day", day.toString()));
            grouped = state.getBoolean("grouped");
        }
        build();
        if (state != null && state.getBundle("editor") != null) openEditor(state.getBundle("editor"));
    }

    @Override protected void onStart() {
        super.onStart();
        if (!isFinishing() && editor == null) load();
    }

    @Override protected void onNewIntent(Intent intent) {
        super.onNewIntent(intent);
        if (editor != null) return;
        setIntent(intent);
        if (readDate(intent)) load();
        else finish();
    }

    @Override protected void onStop() {
        requestId++;
        if (items != null) items.removeAllViews();
        super.onStop();
    }

    @Override protected void onSaveInstanceState(Bundle state) {
        super.onSaveInstanceState(state);
        if (day != null) state.putString("day", day.toString());
        state.putBoolean("grouped", grouped);
        if (editor != null) state.putBundle("editor", editor.state());
    }

    private boolean readDate(Intent intent) {
        if (!"hwarang-widget".equals(intent.getScheme())) return false;
        String[] parts = intent.getData().getSchemeSpecificPart().split("/", -1);
        if ((parts.length < 2 || parts.length > 3) || !("branch".equals(parts[1]) || "mine".equals(parts[1]))) return false;
        try { day = LocalDate.parse(parts[0]); }
        catch (DateTimeException invalidDate) { return false; }
        team = "branch".equals(parts[1]);
        member = parts.length == 3 ? parts[2] : "";
        return member.isEmpty() || (team && WidgetData.validMember(member));
    }

    int dp(int value) {
        return Math.round(value * getResources().getDisplayMetrics().density);
    }

    LinearLayout column() {
        LinearLayout view = new LinearLayout(this);
        view.setOrientation(LinearLayout.VERTICAL);
        return view;
    }

    TextView text(String value, int size, int color) {
        TextView view = new TextView(this);
        view.setText(value);
        view.setTextSize(size);
        view.setTextColor(color);
        return view;
    }

    Button button(String label, Runnable action) {
        Button view = new Button(this);
        view.setAllCaps(false);
        view.setText(label);
        view.setOnClickListener(v -> action.run());
        return view;
    }

    GradientDrawable surface(int color, int radius) {
        GradientDrawable shape = new GradientDrawable();
        shape.setColor(color);
        shape.setCornerRadius(dp(radius));
        return shape;
    }

    void styleButton(Button button, boolean primary, int size) {
        int color = primary ? 0xff006b70 : 0xffe7eff0;
        button.setBackground(new RippleDrawable(ColorStateList.valueOf(0x3300474b), surface(color, 10), null));
        button.setTextColor(primary ? 0xffffffff : 0xff173446);
        button.setTextSize(size);
        button.setMinHeight(dp(48));
        button.setMinimumHeight(dp(48));
        button.setPadding(dp(4), 0, dp(4), 0);
        button.setStateListAnimator(null);
    }

    private void build() {
        LinearLayout body = agendaRoot = column();
        body.setPadding(dp(14), dp(12), dp(14), dp(10));
        body.setBackground(surface(0xfff4f8fc, 16));
        LinearLayout navigation = new LinearLayout(this);
        navigation.setGravity(android.view.Gravity.CENTER_VERTICAL);
        Button previous = button("‹", () -> move(-1));
        previous.setContentDescription("이전 날짜");
        styleButton(previous, false, 24);
        Button next = button("›", () -> move(1));
        next.setContentDescription("다음 날짜");
        styleButton(next, false, 24);
        heading = text("", 19, 0xff173446);
        heading.setGravity(android.view.Gravity.CENTER);
        heading.setSingleLine(true);
        heading.setEllipsize(android.text.TextUtils.TruncateAt.END);
        heading.setTypeface(null, android.graphics.Typeface.BOLD);
        navigation.addView(previous, dp(48), dp(48));
        navigation.addView(heading, new LinearLayout.LayoutParams(0, dp(48), 1));
        navigation.addView(next, dp(48), dp(48));
        body.addView(navigation);
        scope = text("", 13, 0xff315364);
        scope.setGravity(android.view.Gravity.CENTER);
        scope.setSingleLine(true);
        scope.setEllipsize(android.text.TextUtils.TruncateAt.END);
        body.addView(scope, -1, dp(28));
        modes = new LinearLayout(this);
        timeOrder = button("시간순", () -> changeOrder(false));
        memberOrder = button("구성원별", () -> changeOrder(true));
        LinearLayout.LayoutParams timeSize = new LinearLayout.LayoutParams(0, dp(48), 1);
        timeSize.setMarginEnd(dp(8));
        modes.addView(timeOrder, timeSize);
        modes.addView(memberOrder, new LinearLayout.LayoutParams(0, dp(48), 1));
        body.addView(modes, -1, dp(48));
        modes.setVisibility(android.view.View.GONE);
        scroll = new ScrollView(this);
        items = column();
        items.setPadding(dp(4), dp(12), dp(4), dp(8));
        scroll.addView(items);
        android.content.res.Configuration configuration = getResources().getConfiguration();
        boolean tablet = configuration.smallestScreenWidthDp >= 600;
        listHeight = dp(Math.min(tablet ? 360 : 320, Math.max(92, configuration.screenHeightDp - 234)));
        body.addView(scroll, -1, listHeight);
        add = button("＋ 일정 등록", () -> openEditor(null));
        styleButton(add, true, 15);
        LinearLayout.LayoutParams addSize = new LinearLayout.LayoutParams(-1, dp(48));
        addSize.bottomMargin = dp(6);
        body.addView(add, addSize);
        LinearLayout footer = new LinearLayout(this);
        Button close = button("닫기", this::finish);
        Button open = button("캘린더 열기", this::openCalendar);
        styleButton(close, false, 15);
        styleButton(open, true, 15);
        LinearLayout.LayoutParams closeSize = new LinearLayout.LayoutParams(0, dp(48), 1);
        closeSize.setMarginEnd(dp(8));
        footer.addView(close, closeSize);
        footer.addView(open, new LinearLayout.LayoutParams(0, dp(48), 2));
        body.addView(footer);
        setContentView(body);
        getWindow().setLayout(dp(Math.min(tablet ? 520 : 400, configuration.screenWidthDp - 24)), -2);
    }

    private void openEditor(Bundle state) {
        WidgetData data = new WidgetData(this);
        if (data.prefs.getString("uid", "").isEmpty()) return;
        requestId++;
        setFinishOnTouchOutside(false);
        editor = new WidgetEventEditor(this, data, day, state);
        setContentView(editor.view());
        getWindow().setLayout(getWindow().getAttributes().width,
            dp(Math.min(620, getResources().getConfiguration().screenHeightDp - 24)));
        getWindow().setSoftInputMode(android.view.WindowManager.LayoutParams.SOFT_INPUT_ADJUST_RESIZE);
    }

    void returnToAgenda(boolean saved) {
        if (isFinishing() || isDestroyed()) return;
        View focused = getCurrentFocus();
        if (focused != null) getSystemService(android.view.inputmethod.InputMethodManager.class)
            .hideSoftInputFromWindow(focused.getWindowToken(), 0);
        editor = null;
        setFinishOnTouchOutside(true);
        setContentView(agendaRoot);
        getWindow().setLayout(getWindow().getAttributes().width, -2);
        getWindow().setSoftInputMode(android.view.WindowManager.LayoutParams.SOFT_INPUT_ADJUST_UNSPECIFIED);
        if (saved) {
            Toast.makeText(this, "일정을 등록했습니다.", Toast.LENGTH_SHORT).show();
        }
        load();
    }

    @Override public void onBackPressed() {
        if (editor == null) super.onBackPressed();
        else editor.cancel();
    }

    private void updateModes() {
        boolean visible = team && member.isEmpty() && Boolean.TRUE.equals(mayGroup);
        modes.setVisibility(visible ? android.view.View.VISIBLE : android.view.View.GONE);
        scroll.getLayoutParams().height = listHeight - (visible ? dp(48) : 0);
        scroll.requestLayout();
        styleButton(timeOrder, !grouped, 15);
        styleButton(memberOrder, grouped, 15);
        timeOrder.setSelected(!grouped);
        memberOrder.setSelected(grouped);
    }

    private void changeOrder(boolean byMember) {
        if (grouped == byMember) return;
        grouped = byMember;
        updateModes();
        scroll.scrollTo(0, 0);
        if (dayPayload != null) show(dayPayload, team, includeDone);
    }

    private void move(int days) {
        day = day.plusDays(days);
        load();
    }

    private void openCalendar() {
        try {
            startActivity(MonthWidget.calendarLink(day, team).addFlags(Intent.FLAG_ACTIVITY_NEW_TASK));
            finish();
        } catch (ActivityNotFoundException unavailable) {
            Toast.makeText(this, "캘린더를 열 브라우저가 없습니다.", Toast.LENGTH_SHORT).show();
        }
    }

    private void message(String value) {
        items.removeAllViews();
        items.addView(text(value, 15, 0xff315364));
    }

    private void load() {
        int request = ++requestId;
        LocalDate selected = day;
        boolean branch = team;
        String selectedMember = member;
        boolean checkGrouping = branch && selectedMember.isEmpty() && mayGroup == null;
        WidgetData data = new WidgetData(this);
        String uid = data.prefs.getString("uid", "");
        add.setVisibility(uid.isEmpty() ? View.GONE : View.VISIBLE);
        dayPayload = null;
        updateModes();
        heading.setText(day.format(DATE));
        updateScope(-1);
        scroll.scrollTo(0, 0);
        if (uid.isEmpty()) {
            message("위젯 설정에서 화랑 계정을 연결해 주세요.");
            items.addView(button("계정 설정", () -> {
                startActivity(new Intent(this, SetupActivity.class).addFlags(Intent.FLAG_ACTIVITY_NEW_TASK));
                finish();
            }));
            return;
        }
        message("일정을 불러오는 중입니다.");
        WidgetData.io.execute(() -> {
            if (request != requestId || !uid.equals(data.prefs.getString("uid", ""))) return;
            try {
                JSONObject result = data.day(selected, branch, selectedMember);
                runOnUiThread(() -> {
                    if (!active(request, data, uid)) return;
                    dayPayload = result;
                    includeDone = data.prefs.getBoolean("includeDone", true);
                    show(result, branch, includeDone);
                });
                if (checkGrouping && request == requestId) {
                    boolean allowed;
                    try { allowed = data.canGroupBranch(); }
                    catch (Exception unavailable) { return; }
                    boolean canGroup = allowed;
                    runOnUiThread(() -> {
                        if (!active(request, data, uid)) return;
                        mayGroup = canGroup;
                        updateModes();
                        show(result, branch, includeDone);
                    });
                }
            } catch (WidgetData.HttpFailure failure) {
                runOnUiThread(() -> {
                    if (!active(request, data, uid)) return;
                    if (failure.code == 401 || failure.code == 403)
                        message(failure.code == 401 ? "위젯 설정에서 계정 연결을 확인해 주세요." : "이 일정을 볼 권한이 없습니다.");
                    else retry();
                });
            } catch (Exception failure) {
                runOnUiThread(() -> { if (active(request, data, uid)) retry(); });
            }
        });
    }

    private boolean active(int request, WidgetData data, String uid) {
        return request == requestId && !isFinishing() && uid.equals(data.prefs.getString("uid", ""));
    }

    private void retry() {
        message("일정을 불러오지 못했습니다.");
        items.addView(button("다시 시도", this::load));
    }

    private void updateScope(int count) {
        String label = team ? "지점 일정" : "내 일정";
        WidgetData data = new WidgetData(this);
        if (!member.isEmpty() && member.equals(data.member(team))) label += " · " + data.memberLabel();
        if (count >= 0) label += " · " + count + "건";
        if (day.equals(LocalDate.now(MonthWidget.SEOUL))) label += " · 오늘";
        scope.setText(label);
    }

    static String value(JSONObject row, String key) {
        return row.isNull(key) ? "" : row.optString(key).trim();
    }

    private static int timeGroup(JSONObject row) {
        if (row.optBoolean("time_pending")) return 2;
        return value(row, "start_time").isEmpty() ? 0 : 1;
    }

    static String displayTime(JSONObject row) {
        int group = timeGroup(row);
        if (group == 0) return "종일";
        if (group == 2) return "시간 미정";
        String start = value(row, "start_time");
        return start.substring(0, Math.min(5, start.length()));
    }

    private void show(JSONObject payload, boolean branch, boolean includeDone) {
        JSONArray rows = payload.optJSONArray("rows");
        if (rows == null) { retry(); return; }
        List<JSONObject> events = new ArrayList<>();
        for (int i = 0; i < rows.length(); i++) {
            JSONObject row = rows.optJSONObject(i);
            if (row != null && (includeDone || !"완료".equals(value(row, "status")))) events.add(row);
        }
        updateScope(events.size());
        if (events.isEmpty()) {
            message(rows.length() == 0 ? "등록된 일정이 없습니다." : "표시할 일정이 없습니다.");
            return;
        }
        events.sort(Comparator.comparingInt(DayAgendaActivity::timeGroup).thenComparing(row -> value(row, "start_time")));
        Map<String, String> names = new HashMap<>();
        JSONArray roster = payload.optJSONArray("branch");
        for (int i = 0; branch && roster != null && i < roster.length(); i++) {
            JSONObject member = roster.optJSONObject(i);
            if (member != null) names.put(value(member, "member"), value(member, "label"));
        }
        items.removeAllViews();
        if (!branch || !member.isEmpty() || !Boolean.TRUE.equals(mayGroup) || !grouped) {
            for (JSONObject row : events) addEvent(row, branch, names);
            return;
        }
        Map<String, List<JSONObject>> groups = new HashMap<>();
        for (JSONObject row : events) {
            String key = row.optBoolean("common") ? "" : value(row, "owner");
            groups.computeIfAbsent(key, ignored -> new ArrayList<>()).add(row);
        }
        List<String> keys = new ArrayList<>(groups.keySet());
        java.text.Collator korean = java.text.Collator.getInstance(Locale.KOREAN);
        keys.sort(Comparator.comparing((String key) -> !key.isEmpty())
            .thenComparing(key -> groupName(key, names), korean).thenComparing(Comparator.naturalOrder()));
        for (String key : keys) {
            List<JSONObject> group = groups.get(key);
            TextView title = text(groupName(key, names) + " · " + group.size() + "건", 15, 0xff173446);
            title.setTypeface(null, android.graphics.Typeface.BOLD);
            title.setPadding(dp(6), dp(6), dp(6), dp(4));
            if (android.os.Build.VERSION.SDK_INT >= 28) title.setAccessibilityHeading(true);
            items.addView(title);
            for (JSONObject row : group) addEvent(row, false, names);
        }
    }

    private static String groupName(String key, Map<String, String> names) {
        return key.isEmpty() ? "지점 공통" : names.getOrDefault(key, "구성원");
    }

    private void addEvent(JSONObject row, boolean branch, Map<String, String> names) {
        String kind = value(row, "kind");
        String time = displayTime(row);
        String owner = branch ? names.get(value(row, "owner")) : null;
        if (branch && row.optBoolean("common")) owner = "지점 공통";
        String metadata = time + (kind.isEmpty() ? "" : " · " + kind);
        boolean ownerFirst = branch && member.isEmpty();
        if (!ownerFirst && owner != null && !owner.isEmpty()) metadata += " · " + owner;
        String title = row.optBoolean("readable") ? value(row, "title") : "";
        if (title.isEmpty()) title = row.optBoolean("readable") ? (kind.isEmpty() ? "일정" : kind) : "요약만 공개된 일정";
        LinearLayout card = column();
        card.setPadding(dp(10), dp(7), dp(10), dp(7));
        card.setBackground(surface(0xffffffff, 10));
        TextView name = text(title, 17, 0xff173446);
        name.setTypeface(null, android.graphics.Typeface.BOLD);
        if (ownerFirst) {
            LinearLayout rowLayout = new LinearLayout(this);
            TextView clock = text(time, 14, 0xff315364);
            rowLayout.addView(clock, dp(66), -2);
            TextView registrant = text(owner == null || owner.isEmpty() ? "구성원" : owner, 13, 0xff155461);
            registrant.setPadding(dp(5), dp(2), dp(5), dp(2));
            registrant.setBackground(surface(0xffe5f2f1, 5));
            LinearLayout details = column();
            boolean wide = getResources().getConfiguration().smallestScreenWidthDp >= 600
                && getResources().getConfiguration().screenWidthDp >= 480;
            if (wide) {
                LinearLayout.LayoutParams ownerParams = new LinearLayout.LayoutParams(dp(80), -2);
                ownerParams.setMarginEnd(dp(8));
                rowLayout.addView(registrant, ownerParams);
            } else {
                LinearLayout.LayoutParams ownerParams = new LinearLayout.LayoutParams(-2, -2);
                ownerParams.bottomMargin = dp(2);
                details.addView(registrant, ownerParams);
            }
            details.addView(name);
            if (!kind.isEmpty()) details.addView(text(kind, 13, 0xff315364));
            rowLayout.addView(details, new LinearLayout.LayoutParams(0, -2, 1));
            card.addView(rowLayout);
        } else {
            card.addView(name);
            card.addView(text(metadata, 13, 0xff315364));
        }
        LinearLayout.LayoutParams layout = new LinearLayout.LayoutParams(-1, -2);
        layout.bottomMargin = dp(6);
        items.addView(card, layout);
    }
}
