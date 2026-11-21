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
        checkRelease();
    }

    private void checkRelease() {
        android.content.SharedPreferences prefs = getSharedPreferences("release-check", MODE_PRIVATE);
        long now = System.currentTimeMillis();
        if (now - prefs.getLong("checked", 0) < 86400000L) return;
        prefs.edit().putLong("checked", now).apply();
        WidgetData.io.execute(() -> {
            java.net.HttpURLConnection conn = null;
            try {
                conn = (java.net.HttpURLConnection) new java.net.URL(
                    "https://api.github.com/repos/poqter/test/releases?per_page=50").openConnection();
                conn.setConnectTimeout(4000);
                conn.setReadTimeout(4000);
                String current = getPackageManager().getPackageInfo(getPackageName(), 0).versionName;
                try (java.io.InputStream stream = conn.getInputStream();
                     java.util.Scanner reader = new java.util.Scanner(stream, "UTF-8").useDelimiter("\\\\A")) {
                    org.json.JSONArray releases = new org.json.JSONArray(reader.next());
                    for (int i = 0; i < releases.length(); i++) {
                        org.json.JSONObject r = releases.getJSONObject(i);
                        String tag = r.optString("tag_name");
                        if (r.optBoolean("draft") || r.optBoolean("prerelease") ||
                            !tag.matches("widget-v[0-9]+[.][0-9]+[.][0-9]+")) continue;
                        String version = tag.substring(8);
                        if (!newer(version, current)) continue;
                        String url = "https://github.com/poqter/test/releases/download/" + tag + "/hwarang-month-widget.apk";
                        org.json.JSONArray assets = r.getJSONArray("assets");
                        for (int j = 0; j < assets.length(); j++) {
                            if (!url.equals(assets.getJSONObject(j).optString("browser_download_url"))) continue;
                            runOnUiThread(() -> {
                                if (!isFinishing() && !isDestroyed()) new android.app.AlertDialog.Builder(this)
                                    .setTitle("위젯 업데이트 " + version)
                                    .setMessage("새 버전을 내려받고 Android 설치 화면에서 업데이트해 주세요.")
                                    .setNegativeButton("나중에", null)
                                    .setPositiveButton("업데이트", (dialog, which) -> startActivity(new android.content.Intent(
                                        android.content.Intent.ACTION_VIEW, android.net.Uri.parse(url)))).show();
                            });
                            return;
                        }
                    }
                }
            } catch (Exception ignored) { /* Calendar access remains available offline. */ }
            finally { if (conn != null) conn.disconnect(); }
        });
    }

    private static boolean newer(String candidate, String installed) {
        String[] a = candidate.split("[.]"), b = installed.split("[.]");
        for (int i = 0; i < 3; i++) {
            int comparison = Integer.compare(Integer.parseInt(a[i]), Integer.parseInt(b[i]));
            if (comparison != 0) return comparison > 0;
        }
        return false;
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
            email.setHint("WORKSPACE 아이디");
            email.setInputType(InputType.TYPE_CLASS_TEXT | InputType.TYPE_TEXT_FLAG_NO_SUGGESTIONS);
            email.setAutofillHints("username");
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
                if (address.isEmpty() || secret.isEmpty()) { status.setText("아이디와 비밀번호를 입력해 주세요."); return; }
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
                                ? "연결이 지연되고 있습니다. 다시 시도해 주세요." : "아이디와 비밀번호를 확인해 주세요.");
                        });
                    } catch (Exception error) {
                        runOnUiThread(() -> { signIn.setEnabled(true); status.setText("연결하지 못했습니다. 다시 시도해 주세요."); });
                    }
                });
            });
        }
    }
}
