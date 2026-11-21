package com.hwarang.calendarwidget;

import android.content.Context;
import android.content.SharedPreferences;
import android.graphics.Color;
import android.graphics.Typeface;
import android.text.SpannableString;
import android.text.Spanned;
import android.text.style.StyleSpan;
import org.json.JSONObject;
import java.net.URL;
import javax.net.ssl.HttpsURLConnection;
import java.io.InputStream;
import java.io.ByteArrayOutputStream;
import java.nio.charset.StandardCharsets;

final class WidgetStyle {
    private static final String URL_PATH = "https://raw.githubusercontent.com/poqter/test/main/modules/activity/calendar_view/widget-style.json";
    private static final long DAY = 86400000L;
    private final JSONObject values;
    private final JSONObject palette;

    private WidgetStyle(JSONObject values) {
        this.values = values;
        palette = values.optJSONObject("palette");
    }

    private static SharedPreferences cache(Context context) {
        return context.getSharedPreferences("widget_design", Context.MODE_PRIVATE);
    }

    static WidgetStyle read(Context context) {
        try { return new WidgetStyle(new JSONObject(cache(context).getString("style", "{}"))); }
        catch (Exception invalid) { return new WidgetStyle(new JSONObject()); }
    }

    static synchronized void refresh(Context context) {
        SharedPreferences prefs = cache(context);
        long now = System.currentTimeMillis(), last = prefs.getLong("checked", 0);
        if (now >= last && now - last < DAY) return;
        prefs.edit().putLong("checked", now).apply();
        HttpsURLConnection conn = null;
        try {
            conn = (HttpsURLConnection) new URL(URL_PATH).openConnection();
            conn.setConnectTimeout(2500);
            conn.setReadTimeout(2500);
            String etag = prefs.getString("etag", "");
            if (!etag.isEmpty()) conn.setRequestProperty("If-None-Match", etag);
            if (conn.getResponseCode() != 200) return;
            ByteArrayOutputStream bytes = new ByteArrayOutputStream();
            try (InputStream input = conn.getInputStream()) {
                byte[] block = new byte[1024];
                for (int n; (n = input.read(block)) != -1;) {
                    if (bytes.size() + n > 8192) return;
                    bytes.write(block, 0, n);
                }
            }
            JSONObject style = new JSONObject(bytes.toString(StandardCharsets.UTF_8.name()));
            if (style.optInt("schema") == 1 && style.optJSONObject("palette") != null)
                prefs.edit().putString("style", style.toString()).putString("etag", conn.getHeaderField("ETag")).apply();
        } catch (Exception offline) { /* Keep the local design. */ }
        finally { if (conn != null) conn.disconnect(); }
    }

    int size(String key, int fallback, int min, int max) {
        return Math.max(min, Math.min(max, values.optInt(key, fallback)));
    }
    private static int color(JSONObject source, String key, int fallback) {
        String value = source == null ? "" : source.optString(key);
        return value.matches("#[0-9a-fA-F]{6}") ? Color.parseColor(value) : fallback;
    }
    int color(String key, int fallback) { return color(values, key, fallback); }
    int accent(String kind) {
        if ("청약".equals(kind) || "제안".equals(kind)) kind = "PC";
        int fallback = MonthWidget.DOTS.getOrDefault(kind, 0xff687789);
        if (!MonthWidget.DOTS.containsKey(kind) && !"common".equals(kind)) kind = "기타";
        return color(palette, kind, "common".equals(kind) ? 0xff9d2455 : fallback);
    }
    String webLabel() {
        String label = values.optString("webLabel","웹 캘린더 ↗").trim();
        return label.isEmpty() || label.length()>14 ? "웹 캘린더 ↗" : label;
    }
    boolean centered() { return !"left".equals(values.optString("stateAlign")); }
    CharSequence styled(String value, String key, boolean bold) {
        if (!values.optBoolean(key, bold)) return value;
        SpannableString result = new SpannableString(value);
        result.setSpan(new StyleSpan(Typeface.BOLD), 0, result.length(), Spanned.SPAN_EXCLUSIVE_EXCLUSIVE);
        return result;
    }
}
