package com.hwarang.calendarwidget;

import android.app.TimePickerDialog;
import android.os.Bundle;
import android.text.InputFilter;
import android.view.View;
import android.widget.AdapterView;
import android.widget.ArrayAdapter;
import android.widget.Button;
import android.widget.EditText;
import android.widget.LinearLayout;
import android.widget.ScrollView;
import android.widget.Spinner;
import android.widget.TextView;
import java.time.LocalDate;
import java.time.LocalTime;
import java.time.format.DateTimeFormatter;
import java.util.Locale;
import java.util.UUID;
import org.json.JSONObject;

final class WidgetEventEditor {
    private static final int COLOR = 0xff173446;
    private static final String[] KINDS = {"미분류", "TA", "AP", "PC", "CS", "청약", "교육", "회의", "휴무", "기타"};
    private static final String[] MODES = {"시간 미정", "시간 지정", "종일"};
    private static final DateTimeFormatter CLOCK = DateTimeFormatter.ofPattern("HH:mm:ss", Locale.ROOT);
    private final DayAgendaActivity activity;
    private final WidgetData data;
    private final LocalDate day;
    private final String uid;
    private final String id;
    private final LinearLayout root;
    private final LinearLayout more;
    private final EditText title;
    private final EditText place;
    private final EditText note;
    private final Spinner kind;
    private final Spinner mode;
    private final Button startButton;
    private final Button endButton;
    private final Button extra;
    private final Button cancel;
    private final Button save;
    private final TextView status;
    private LocalTime start;
    private LocalTime end;
    private String acceptedOverlap;
    private boolean saving;

    WidgetEventEditor(DayAgendaActivity activity, WidgetData data, LocalDate day, Bundle restored) {
        this.activity = activity;
        this.data = data;
        this.day = day;
        uid = data.prefs.getString("uid", "");
        Bundle state = restored != null && uid.equals(restored.getString("uid")) ? restored : new Bundle();
        id = state.getString("id", UUID.randomUUID().toString());
        start = readTime(state, "start");
        end = readTime(state, "end");
        root = activity.column();
        root.setPadding(activity.dp(14), activity.dp(12), activity.dp(14), activity.dp(10));
        root.setBackground(activity.surface(0xfff4f8fc, 16));
        root.setFocusableInTouchMode(true);
        root.requestFocus();
        String date = day.format(DateTimeFormatter.ofPattern("M월 d일 (E)", Locale.KOREAN));
        root.addView(activity.text(date + " 일정 등록", 19, COLOR));
        root.addView(activity.text("내 일정으로 저장됩니다.", 13, COLOR));
        ScrollView scroll = new ScrollView(activity);
        LinearLayout fields = activity.column();
        scroll.addView(fields);
        root.addView(scroll, new LinearLayout.LayoutParams(-1, 0, 1));
        title = field(fields, "제목", state.getString("title", ""), 200, true);
        mode = options(fields, "시간", MODES, state.getInt("mode"));
        startButton = activity.button("", () -> chooseTime(false));
        fields.addView(startButton);
        kind = options(fields, "활동 종류", KINDS, state.getInt("kind"));

        extra = activity.button("", () -> expand(moreIsClosed()));
        fields.addView(extra);
        more = activity.column();
        endButton = activity.button("", () -> chooseTime(true));
        more.addView(endButton);
        place = field(more, "장소", state.getString("place", ""), 500, true);
        note = field(more, "메모", state.getString("note", ""), 2000, false);
        fields.addView(more);
        expand(state.getBoolean("expanded"));
        status = activity.text("", 14, COLOR);
        status.setAccessibilityLiveRegion(View.ACCESSIBILITY_LIVE_REGION_POLITE);
        fields.addView(status);

        LinearLayout footer = new LinearLayout(activity);
        cancel = activity.button("취소", this::cancel);
        save = activity.button("저장", this::submit);
        activity.styleButton(cancel, false, 15);
        activity.styleButton(save, true, 15);
        LinearLayout.LayoutParams cancelSize = new LinearLayout.LayoutParams(0, activity.dp(48), 1);
        cancelSize.setMarginEnd(activity.dp(8));
        footer.addView(cancel, cancelSize);
        footer.addView(save, new LinearLayout.LayoutParams(0, activity.dp(48), 2));
        root.addView(footer);

        AdapterView.OnItemSelectedListener listener = new AdapterView.OnItemSelectedListener() {
            @Override public void onItemSelected(AdapterView<?> parent, View view, int position, long id) { updateType(); }
            @Override public void onNothingSelected(AdapterView<?> parent) {}
        };
        kind.setOnItemSelectedListener(listener);
        mode.setOnItemSelectedListener(listener);
        updateType();
    }

    View view() { return root; }

    private static LocalTime readTime(Bundle state, String key) {
        String value = state.getString(key);
        return value == null ? null : LocalTime.parse(value);
    }

    Bundle state() {
        Bundle values = new Bundle();
        values.putString("uid", uid);
        values.putString("id", id);
        values.putString("title", title.getText().toString());
        values.putString("place", place.getText().toString());
        values.putString("note", note.getText().toString());
        values.putInt("kind", kind.getSelectedItemPosition());
        values.putInt("mode", mode.getSelectedItemPosition());
        if (start != null) values.putString("start", start.toString());
        if (end != null) values.putString("end", end.toString());
        values.putBoolean("expanded", !moreIsClosed());
        return values;
    }

    private EditText field(LinearLayout parent, String label, String value, int limit, boolean singleLine) {
        TextView caption = activity.text(label, 13, COLOR);
        EditText input = new EditText(activity);
        input.setId(View.generateViewId());
        caption.setLabelFor(input.getId());
        parent.addView(caption);
        input.setSingleLine(singleLine);
        input.setFilters(new InputFilter[]{new InputFilter.LengthFilter(limit)});
        input.setText(value);
        input.setTextSize(16);
        parent.addView(input);
        return input;
    }

    private Spinner options(LinearLayout parent, String label, String[] values, int selected) {
        TextView caption = activity.text(label, 13, COLOR);
        Spinner input = new Spinner(activity);
        input.setId(View.generateViewId());
        caption.setLabelFor(input.getId());
        parent.addView(caption);
        ArrayAdapter<String> adapter = new ArrayAdapter<>(activity, android.R.layout.simple_spinner_item, values);
        adapter.setDropDownViewResource(android.R.layout.simple_spinner_dropdown_item);
        input.setAdapter(adapter);
        input.setSelection(selected);
        parent.addView(input, -1, activity.dp(48));
        return input;
    }

    private boolean moreIsClosed() { return more.getVisibility() == View.GONE; }

    private void expand(boolean expanded) {
        more.setVisibility(expanded ? View.VISIBLE : View.GONE);
        extra.setText(expanded ? "추가 정보 닫기 ▴" : "추가 정보 ▾");
    }

    private boolean leave() { return "휴무".equals(kind.getSelectedItem()); }

    private void updateType() {
        boolean timed = !leave() && mode.getSelectedItemPosition() == 1;
        if (leave()) mode.setSelection(2);
        title.setEnabled(!saving && !leave());
        mode.setEnabled(!saving && !leave());
        startButton.setVisibility(timed ? View.VISIBLE : View.GONE);
        endButton.setVisibility(timed ? View.VISIBLE : View.GONE);
        startButton.setText(start == null ? "시작 시간 선택" : "시작 " + start.format(CLOCK).substring(0, 5));
        endButton.setText(end == null ? "종료 시간 선택 · 선택 사항" : "종료 " + end.format(CLOCK).substring(0, 5));
    }

    private void chooseTime(boolean isEnd) {
        LocalTime old = isEnd ? end : start;
        if (old == null) old = start == null ? LocalTime.of(9, 0) : start;
        TimePickerDialog picker = new TimePickerDialog(activity, (view, hour, minute) -> {
            if (isEnd) end = LocalTime.of(hour, minute);
            else start = LocalTime.of(hour, minute);
            updateType();
        }, old.getHour(), old.getMinute(), true);
        if (isEnd && end != null) picker.setButton(TimePickerDialog.BUTTON_NEUTRAL, "지우기", (dialog, which) -> {
            end = null;
            updateType();
        });
        picker.show();
    }

    private JSONObject payload() throws Exception {
        String name = leave() ? "휴무" : title.getText().toString().trim();
        if (name.isEmpty()) throw new IllegalArgumentException("제목을 입력해 주세요.");
        int selection = leave() ? 2 : mode.getSelectedItemPosition();
        if (selection == 1 && start == null) throw new IllegalArgumentException("시작 시간을 선택해 주세요.");
        if (selection == 1 && end != null && !end.isAfter(start)) {
            expand(true);
            throw new IllegalArgumentException("종료 시간은 시작 시간보다 늦어야 합니다.");
        }
        return new JSONObject().put("id", id).put("day", day.toString()).put("title", name)
            .put("kind", kind.getSelectedItem().toString()).put("time_pending", selection == 0)
            .put("start_time", selection == 1 ? start.format(CLOCK) : JSONObject.NULL)
            .put("end_time", selection == 1 && end != null ? end.format(CLOCK) : JSONObject.NULL)
            .put("place", place.getText().toString().trim()).put("note", note.getText().toString().trim());
    }

    private void busy(boolean active) {
        saving = active;
        cancel.setEnabled(!active);
        save.setEnabled(!active);
        kind.setEnabled(!active);
        startButton.setEnabled(!active);
        endButton.setEnabled(!active);
        place.setEnabled(!active);
        note.setEnabled(!active);
        extra.setEnabled(!active);
        updateType();
    }

    private void submit() {
        if (saving) return;
        final JSONObject draft;
        try { draft = payload(); }
        catch (IllegalArgumentException invalid) { status.setText(invalid.getMessage()); return; }
        catch (Exception failure) { status.setText("일정 입력을 확인해 주세요."); return; }
        busy(true);
        status.setText("저장 중…");
        String overlap = acceptedOverlap;
        WidgetData.io.execute(() -> {
            try {
                String confirmation = data.createEvent(uid, draft, overlap);
                if (confirmation == null) {
                    MonthWidget.schedule(activity.getApplicationContext());
                    activity.runOnUiThread(() -> activity.returnToAgenda(true));
                } else {
                    activity.runOnUiThread(() -> {
                        acceptedOverlap = confirmation;
                        busy(false);
                        status.setText("기존 일정과 시간이 겹칩니다. 그대로 등록하려면 저장을 다시 눌러 주세요.");
                    });
                }
            } catch (Exception failure) {
                activity.runOnUiThread(() -> {
                    busy(false);
                    boolean denied = failure instanceof WidgetData.HttpFailure
                        && (((WidgetData.HttpFailure) failure).code == 401 || ((WidgetData.HttpFailure) failure).code == 403);
                    status.setText(denied ? "계정 연결과 일정 등록 권한을 확인해 주세요."
                        : "저장을 확인하지 못했습니다. 입력을 유지한 채 다시 시도해 주세요.");
                });
            }
        });
    }

    void cancel() {
        if (!saving) activity.returnToAgenda(false);
    }
}
