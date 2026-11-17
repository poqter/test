package com.hwarang.calendarwidget;

import android.content.SharedPreferences;
import java.io.ByteArrayOutputStream;
import java.io.InputStream;
import java.net.HttpURLConnection;
import java.net.URL;
import org.json.JSONObject;

final class WidgetStyle {
    private static final String URL_PATH =
        "https://hwarang-calendar.streamlit.app/app/static/calendar-widget-style.json";
    private static final String CACHE = "wide_style";
    private static final String CHECKED = "wide_style_checked";
    private static final long CHECK_INTERVAL = 15 * 60 * 1000L;

    final int entrySp;
    final int dateSp;
    final int paddingDp;
    final int maxEntries;

    private WidgetStyle(JSONObject config) {
        entrySp = bounded(config, "entrySp", 16, 12, 18);
        dateSp = bounded(config, "dateSp", 20, 16, 22);
        paddingDp = bounded(config, "rowPaddingDp", 3, 1, 5);
        maxEntries = bounded(config, "maxEntries", 4, 1, 4);
    }

    private static int bounded(JSONObject config, String field, int fallback, int min, int max) {
        return Math.max(min, Math.min(max, config.optInt(field, fallback)));
    }

    static WidgetStyle read(SharedPreferences prefs) {
        try { return new WidgetStyle(new JSONObject(prefs.getString(CACHE, "{}"))); }
        catch (org.json.JSONException invalid) { return new WidgetStyle(new JSONObject()); }
    }

    static void allowRefresh(SharedPreferences prefs) {
        prefs.edit().remove(CHECKED).apply();
    }

    static boolean refresh(SharedPreferences prefs) {
        long now = System.currentTimeMillis();
        long previous = prefs.getLong(CHECKED, 0);
        if (now >= previous && now - previous < CHECK_INTERVAL) return false;
        prefs.edit().putLong(CHECKED, now).apply();
        try {
            HttpURLConnection connection = (HttpURLConnection) new URL(URL_PATH).openConnection();
            try {
                connection.setConnectTimeout(1800);
                connection.setReadTimeout(1800);
                connection.setInstanceFollowRedirects(false);
                if (connection.getResponseCode() != 200) return false;
                try (InputStream input = connection.getInputStream()) {
                    ByteArrayOutputStream bytes = new ByteArrayOutputStream();
                    byte[] chunk = new byte[512];
                    for (int count; (count = input.read(chunk)) != -1;) {
                        if (bytes.size() + count > 4096) return false;
                        bytes.write(chunk, 0, count);
                    }
                    JSONObject config = new JSONObject(bytes.toString("UTF-8"));
                    String updated = config.toString();
                    if (config.optInt("schema") != 1 || updated.equals(prefs.getString(CACHE, ""))) return false;
                    prefs.edit().putString(CACHE, updated).apply();
                    return true;
                }
            } finally {
                connection.disconnect();
            }
        } catch (java.io.IOException | org.json.JSONException unavailable) {
            return false; // Keep the last valid style until the endpoint is reachable again.
        }
    }
}
