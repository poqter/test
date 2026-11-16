package com.hwarang.calendarwidget;

import android.app.Activity;
import android.appwidget.AppWidgetManager;
import android.content.ComponentName;
import android.os.Bundle;
import android.text.InputType;
import android.widget.Button;
import android.widget.CheckBox;
import android.widget.EditText;
import android.widget.LinearLayout;
import android.widget.ScrollView;
import android.widget.TextView;

public final class SetupActivity extends Activity {
    @Override public void onCreate(Bundle state) {
        super.onCreate(state);
        show("");
    }

    private void show(String message) {
        WidgetData data = new WidgetData(this);
        ScrollView scroll = new ScrollView(this);
        LinearLayout body = new LinearLayout(this);
        body.setOrientation(LinearLayout.VERTICAL);
        int pad = Math.round(getResources().getDisplayMetrics().density * 24);
        body.setPadding(pad, pad * 2, pad, pad);
        scroll.addView(body);
        setContentView(scroll);
        TextView title = new TextView(this);
        title.setTextSize(24);
        title.setText("화랑 월간 달력");
        body.addView(title);
        TextView status = new TextView(this);
        status.setText(message);
        body.addView(status);
        if (data.prefs.contains("session")) {
            CheckBox done = new CheckBox(this);
            done.setText("완료 일정 포함");
            done.setChecked(data.prefs.getBoolean("includeDone", true));
            done.setOnCheckedChangeListener((button, enabled) -> {
                data.setIncludeDone(enabled); MonthWidget.paintAll(this);
            });
            body.addView(done);
            Button pin = new Button(this);
            pin.setText("홈 화면에 위젯 추가");
            pin.setOnClickListener(v -> {
                AppWidgetManager manager = AppWidgetManager.getInstance(this);
                if (!manager.isRequestPinAppWidgetSupported() || !manager.requestPinAppWidget(
                    new ComponentName(this, MonthWidget.class), null, null))
                    status.setText("홈 화면을 길게 눌러 위젯 목록에서 화랑 월간 달력을 추가해 주세요.");
            });
            body.addView(pin);
            Button signOut = new Button(this);
            signOut.setText("계정 연결 해제");
            signOut.setOnClickListener(v -> {
                signOut.setEnabled(false);
                WidgetData.io.execute(() -> {
                    try { data.signOut(); } catch (Exception ignored) { }
                    MonthWidget.paintAll(this);
                    runOnUiThread(() -> show("이 기기에서 계정 연결을 해제했습니다."));
                });
            });
            body.addView(signOut);
            MonthWidget.schedule(this);
        } else {
            EditText email = new EditText(this);
            email.setSingleLine();
            email.setHint("화랑 계정 이메일");
            email.setInputType(InputType.TYPE_CLASS_TEXT | InputType.TYPE_TEXT_VARIATION_EMAIL_ADDRESS);
            email.setAutofillHints("emailAddress");
            body.addView(email);
            EditText password = new EditText(this);
            password.setSingleLine();
            password.setHint("비밀번호");
            password.setInputType(InputType.TYPE_CLASS_TEXT | InputType.TYPE_TEXT_VARIATION_PASSWORD);
            password.setAutofillHints("password");
            body.addView(password);
            Button signIn = new Button(this);
            signIn.setText("캘린더 계정 연결");
            body.addView(signIn);
            signIn.setOnClickListener(v -> {
                String address = email.getText().toString().trim(), secret = password.getText().toString();
                if (address.isEmpty() || secret.isEmpty()) { status.setText("이메일과 비밀번호를 입력해 주세요."); return; }
                signIn.setEnabled(false);
                password.setText("");
                WidgetData.io.execute(() -> {
                    try {
                        data.signIn(address, secret);
                        data.prefs.edit().remove("state").apply();
                        MonthWidget.paintAll(this);
                        runOnUiThread(() -> show("캘린더 계정을 연결했습니다."));
                    } catch (WidgetData.HttpFailure error) {
                        runOnUiThread(() -> {
                            signIn.setEnabled(true);
                            status.setText(error.code == 403 ? "캘린더 이용 권한을 확인해 주세요." : error.code == 429
                                ? "잠시 후 다시 시도해 주세요." : error.code >= 500
                                ? "연결이 지연되고 있습니다. 다시 시도해 주세요." : "이메일과 비밀번호를 확인해 주세요.");
                        });
                    } catch (Exception error) {
                        runOnUiThread(() -> { signIn.setEnabled(true); status.setText("연결하지 못했습니다. 다시 시도해 주세요."); });
                    }
                });
            });
        }
    }
}
