package com.hwarang.calendarwidget;

import android.app.Activity;
import android.os.Bundle;
import android.text.Editable;
import android.text.TextWatcher;
import android.view.View;
import android.view.WindowManager;
import android.widget.ArrayAdapter;
import android.widget.Button;
import android.widget.EditText;
import android.widget.LinearLayout;
import android.widget.ListView;
import android.widget.TextView;
import java.util.ArrayList;
import java.util.Comparator;
import java.util.List;
import java.util.Locale;
import org.json.JSONArray;
import org.json.JSONObject;

public final class MemberSearchActivity extends Activity {
    private static final class Member {
        final String id;
        final String label;

        Member(String id, String label) {
            this.id = id;
            this.label = label;
        }
    }

    private final List<Member> members = new ArrayList<>();
    private final List<Member> matches = new ArrayList<>();
    private WidgetData data;
    private String uid;
    private EditText query;
    private TextView status;
    private Button retry;
    private ArrayAdapter<String> adapter;
    private boolean loaded;

    @Override public void onCreate(Bundle state) {
        super.onCreate(state);
        data = new WidgetData(this);
        uid = data.prefs.getString("uid", "");
        if (uid.isEmpty()) { finish(); return; }

        LinearLayout content = new LinearLayout(this);
        content.setOrientation(LinearLayout.VERTICAL);
        content.setPadding(dp(16), dp(12), dp(16), dp(12));
        TextView heading = new TextView(this);
        heading.setText("구성원 검색");
        heading.setTextSize(20);
        content.addView(heading);

        query = new EditText(this);
        query.setHint("이름을 입력하세요");
        query.setSingleLine(true);
        query.setInputType(android.text.InputType.TYPE_CLASS_TEXT
            | android.text.InputType.TYPE_TEXT_VARIATION_PERSON_NAME);
        content.addView(query);
        status = new TextView(this);
        status.setAccessibilityLiveRegion(View.ACCESSIBILITY_LIVE_REGION_POLITE);
        content.addView(status);

        ListView list = new ListView(this);
        adapter = new ArrayAdapter<>(this, android.R.layout.simple_list_item_1);
        list.setAdapter(adapter);
        list.setOnItemClickListener((parent, view, position, id) -> select(matches.get(position)));
        int screenHeight = getResources().getConfiguration().screenHeightDp;
        content.addView(list, -1, dp(Math.min(300, Math.max(70, screenHeight - 190))));
        query.addTextChangedListener(new TextWatcher() {
            @Override public void beforeTextChanged(CharSequence text, int start, int count, int after) {}
            @Override public void onTextChanged(CharSequence text, int start, int before, int count) { filter(); }
            @Override public void afterTextChanged(Editable text) {}
        });

        LinearLayout actions = new LinearLayout(this);
        actions.addView(button("전체", () -> select(new Member("", ""))), new LinearLayout.LayoutParams(0, dp(48), 1));
        retry = button("다시 시도", this::load);
        retry.setVisibility(View.GONE);
        actions.addView(retry, new LinearLayout.LayoutParams(0, dp(48), 1));
        actions.addView(button("닫기", this::finish), new LinearLayout.LayoutParams(0, dp(48), 1));
        content.addView(actions);
        content.setFocusableInTouchMode(true);
        content.requestFocus();
        setContentView(content);
        int screenWidth = getResources().getConfiguration().screenWidthDp;
        getWindow().setLayout(dp(Math.min(460, screenWidth - 24)), -2);
        getWindow().setSoftInputMode(WindowManager.LayoutParams.SOFT_INPUT_ADJUST_RESIZE
            | WindowManager.LayoutParams.SOFT_INPUT_STATE_ALWAYS_HIDDEN);
        load();
    }

    private int dp(int value) {
        return Math.round(value * getResources().getDisplayMetrics().density);
    }

    private Button button(String label, Runnable action) {
        Button button = new Button(this);
        button.setText(label);
        button.setAllCaps(false);
        button.setOnClickListener(view -> action.run());
        return button;
    }

    private boolean active() {
        return !isFinishing() && !isDestroyed() && uid.equals(data.prefs.getString("uid", ""));
    }

    private void load() {
        status.setText("구성원을 불러오는 중입니다.");
        retry.setVisibility(View.GONE);
        WidgetData.io.execute(() -> {
            if (!uid.equals(data.prefs.getString("uid", ""))) return;
            try {
                JSONArray roster = data.branchMembers();
                List<Member> found = new ArrayList<>();
                for (int i = 0; i < roster.length(); i++) {
                    JSONObject row = roster.getJSONObject(i);
                    String id = row.optString("member");
                    String label = DayAgendaActivity.value(row, "label");
                    if (WidgetData.validMember(id) && !label.isEmpty()) found.add(new Member(id, label));
                }
                found.sort(Comparator.comparing(member -> member.label, java.text.Collator.getInstance(Locale.KOREAN)));
                runOnUiThread(() -> {
                    if (!active()) return;
                    members.clear();
                    members.addAll(found);
                    loaded = true;
                    filter();
                });
            } catch (Exception failure) {
                runOnUiThread(() -> {
                    if (!active()) return;
                    status.setText("구성원을 불러오지 못했습니다.");
                    retry.setVisibility(View.VISIBLE);
                });
            }
        });
    }

    private void filter() {
        if (!loaded) return;
        String text = query.getText().toString().trim().toLowerCase(Locale.ROOT);
        matches.clear();
        adapter.setNotifyOnChange(false);
        adapter.clear();
        for (Member member : members) {
            if (!member.label.toLowerCase(Locale.ROOT).contains(text)) continue;
            matches.add(member);
            adapter.add(member.label);
        }
        adapter.notifyDataSetChanged();
        status.setText(matches.isEmpty() ? "검색 결과가 없습니다." : "");
    }

    private void select(Member member) {
        if (active()) {
            data.selectMember(member.id, member.label);
            data.setTeam(true);
            MonthWidget.paintAll(this);
            MonthWidget.schedule(this);
        }
        finish();
    }
}
