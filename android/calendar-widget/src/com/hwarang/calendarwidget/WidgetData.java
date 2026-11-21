package com.hwarang.calendarwidget;

import android.content.Context;
import android.content.SharedPreferences;
import android.security.keystore.KeyGenParameterSpec;
import android.security.keystore.KeyProperties;
import android.util.Base64;
import java.io.InputStream;
import java.net.HttpURLConnection;
import java.net.URL;
import java.nio.charset.StandardCharsets;
import java.security.KeyStore;
import java.time.YearMonth;
import java.util.concurrent.Executors;
import java.util.concurrent.ExecutorService;
import javax.crypto.Cipher;
import javax.crypto.KeyGenerator;
import javax.crypto.SecretKey;
import javax.crypto.spec.GCMParameterSpec;
import org.json.JSONArray;
import org.json.JSONObject;

final class WidgetData {
    static final ExecutorService io = Executors.newSingleThreadExecutor();
    private static final String ROOT = "https://zaynrfzzrtuiherbhoee.supabase.co";
    private static final String KEY = "sb_publishable_NdoOryxAxzTedYSewD0GGA_lHiOG2bx";
    private static final String ALIAS = "hwarang-calendar-widget";
    final SharedPreferences prefs;

    WidgetData(Context context) {
        prefs = context.getSharedPreferences("calendar_widget", Context.MODE_PRIVATE);
    }

    static final class HttpFailure extends Exception {
        final int code;
        HttpFailure(int code) { this.code = code; }
    }

    private static JSONObject request(String path, String token, JSONObject body) throws Exception {
        HttpURLConnection conn = (HttpURLConnection) new URL(ROOT + path).openConnection();
        try {
            conn.setInstanceFollowRedirects(false);
            conn.setConnectTimeout(3500);
            conn.setReadTimeout(3500);
            conn.setRequestProperty("apikey", KEY);
            conn.setRequestProperty("X-Hwarang-Widget-Version", "0.2.10");
            
            if (token != null) conn.setRequestProperty("Authorization", "Bearer " + token);
            if (body != null) {
                conn.setRequestMethod("POST");
                conn.setRequestProperty("Content-Type", "application/json");
                conn.setDoOutput(true);
                try (java.io.OutputStream out = conn.getOutputStream()) {
                    out.write(body.toString().getBytes(StandardCharsets.UTF_8));
                }
            }
            int status = conn.getResponseCode();
            if (status < 200 || status >= 300) throw new HttpFailure(status);
            if (status == 204) return new JSONObject();
            try (InputStream in = conn.getInputStream()) {
                java.io.ByteArrayOutputStream bytes = new java.io.ByteArrayOutputStream();
                byte[] chunk = new byte[8192];
                for (int n; (n = in.read(chunk)) != -1;) bytes.write(chunk, 0, n);
                return new JSONObject(bytes.toString("UTF-8"));
            }
        } finally {
            conn.disconnect();
        }
    }

    private SecretKey key() throws Exception {
        KeyStore store = KeyStore.getInstance("AndroidKeyStore");
        store.load(null);
        SecretKey key = (SecretKey) store.getKey(ALIAS, null);
        if (key != null) return key;
        KeyGenerator generator = KeyGenerator.getInstance(KeyProperties.KEY_ALGORITHM_AES, "AndroidKeyStore");
        generator.init(new KeyGenParameterSpec.Builder(ALIAS, KeyProperties.PURPOSE_ENCRYPT | KeyProperties.PURPOSE_DECRYPT)
            .setBlockModes(KeyProperties.BLOCK_MODE_GCM).setEncryptionPaddings(KeyProperties.ENCRYPTION_PADDING_NONE).build());
        return generator.generateKey();
    }

    private JSONObject loadSession() throws Exception { return decrypt(prefs.getString("session","")); }
    private JSONObject decrypt(String encrypted) throws Exception {
        if (encrypted.isEmpty()) return null;
        String[] parts = encrypted.split(":", 2);
        Cipher cipher = Cipher.getInstance("AES/GCM/NoPadding");
        cipher.init(Cipher.DECRYPT_MODE, key(), new GCMParameterSpec(128, Base64.decode(parts[0], Base64.NO_WRAP)));
        return new JSONObject(new String(cipher.doFinal(Base64.decode(parts[1], Base64.NO_WRAP)), StandardCharsets.UTF_8));
    }

    JSONObject cachedMonth(YearMonth month, boolean team) throws Exception {
        String raw=prefs.getString(cacheKey(month,team),"{}");
        return raw.startsWith("{") ? new JSONObject(raw) : decrypt(raw);
    }
    private String encrypt(JSONObject value) throws Exception {
        Cipher cipher=Cipher.getInstance("AES/GCM/NoPadding");
        cipher.init(Cipher.ENCRYPT_MODE,key());
        return Base64.encodeToString(cipher.getIV(),Base64.NO_WRAP)+":"+Base64.encodeToString(cipher.doFinal(value.toString().getBytes(StandardCharsets.UTF_8)),Base64.NO_WRAP);
    }
    private JSONObject saveSession(JSONObject response, String previousUser) throws Exception {
        JSONObject user = response.optJSONObject("user");
        String uid = user == null ? previousUser : user.getString("id");
        if (uid == null || (previousUser != null && !previousUser.equals(uid))) throw new HttpFailure(401);
        JSONObject session = new JSONObject().put("uid", uid).put("access", response.getString("access_token"))
            .put("refresh", response.getString("refresh_token"))
            .put("expires", response.optLong("expires_at", System.currentTimeMillis() / 1000 + response.optLong("expires_in", 3600)));
        Cipher cipher = Cipher.getInstance("AES/GCM/NoPadding");
        cipher.init(Cipher.ENCRYPT_MODE, key());
        byte[] encrypted = cipher.doFinal(session.toString().getBytes(StandardCharsets.UTF_8));
        if (!prefs.edit().putString("uid", uid).putString("session", Base64.encodeToString(cipher.getIV(), Base64.NO_WRAP)
            + ":" + Base64.encodeToString(encrypted, Base64.NO_WRAP)).commit()) throw new java.io.IOException("Could not store session");
        if (user != null && user.has("user_metadata")) {
            JSONObject metadata = user.optJSONObject("user_metadata");
            prefs.edit().putBoolean("sunday", metadata != null && metadata.optInt("hwarang_calendar_month_week_start", 1) == 0).apply();
        }
        return session;
    }

    void signIn(String loginId, String password) throws Exception {
        JSONObject response = request("/functions/v1/widget-login", null,
            new JSONObject().put("login_id", loginId).put("password", password));
        // Verify calendar access before retaining this device session.
        month(response.getString("access_token"), MonthWidget.currentMonth(), false);
        clear();
        JSONObject session = saveSession(response, null);
        String uid = session.getString("uid");
        prefs.edit().putBoolean("team", prefs.getBoolean("team:" + uid, false))
            .putBoolean("includeDone", prefs.getBoolean("done:" + uid, true)).commit();
    }

    void signOut() throws Exception {
        JSONObject old;
        try { old = loadSession(); } finally { clear(); }
        if (old != null) {
            if (old.getLong("expires") <= System.currentTimeMillis() / 1000 + 30) {
                old = request("/auth/v1/token?grant_type=refresh_token", null,
                    new JSONObject().put("refresh_token", old.getString("refresh")));
                request("/auth/v1/logout?scope=local", old.getString("access_token"), new JSONObject());
            } else {
                request("/auth/v1/logout?scope=local", old.getString("access"), new JSONObject());
            }
        }
    }

    void clear() {
        lastDay = null;
        lastSession = null;
        prefs.edit().remove("canCommon").apply();
        SharedPreferences.Editor edit = prefs.edit().remove("session").remove("uid").remove("sunday").remove("includeDone").putBoolean("team", false);
        for (String name : prefs.getAll().keySet()) if (name.startsWith("month:")) edit.remove(name);
        edit.commit();
    }

    private JSONObject renew(JSONObject session) throws Exception {
        try {
            return saveSession(request("/auth/v1/token?grant_type=refresh_token", null,
                new JSONObject().put("refresh_token", session.getString("refresh"))), session.getString("uid"));
        } catch (HttpFailure failure) {
            if (failure.code == 400 || failure.code == 401 || failure.code == 403) throw new HttpFailure(401);
            throw failure;
        }
    }

    void setTeam(boolean team) {
        String uid = prefs.getString("uid", "");
        SharedPreferences.Editor edit = prefs.edit().putBoolean("team", team);
        if (!uid.isEmpty()) edit.putBoolean("team:" + uid, team);
        edit.commit();
    }

    void setIncludeDone(boolean includeDone) {
        String uid = prefs.getString("uid", "");
        SharedPreferences.Editor edit = prefs.edit().putBoolean("includeDone", includeDone);
        if (!uid.isEmpty()) edit.putBoolean("done:" + uid, includeDone);
        edit.apply();
    }

    String cacheKey(YearMonth month, boolean team) { return "month:" + month + ":" + team; }

    private static JSONObject month(String token, YearMonth month, boolean team) throws Exception {
        return request("/rest/v1/rpc/sales_widget_month", token, new JSONObject()
            .put("first_day", month.atDay(1).toString()).put("last_day", month.atEndOfMonth().toString())
            .put("p_team", team));
    }

    void refresh(YearMonth month, boolean team) throws Exception {
        lastDay = null;
        JSONObject session;
        try { session = loadSession(); }
        catch (Exception invalidStore) { throw new HttpFailure(401); }
        if (session == null) throw new HttpFailure(401);
        if (session.getLong("expires") <= System.currentTimeMillis() / 1000 + 30) session = renew(session);
        try {
            fetchMonth(session, month, team);
        } catch (HttpFailure failure) {
            if (failure.code != 401) throw failure;
            fetchMonth(renew(session), month, team);
        }
    }


    JSONObject call(String function, JSONObject args) throws Exception {
        lastDay = null;
        JSONObject session=loadSession();
        if(session==null)throw new HttpFailure(401);
        if(session.getLong("expires")<=System.currentTimeMillis()/1000+30)session=renew(session);
        return request("/rest/v1/rpc/"+function,session.getString("access"),args);
    }
    // Accessed by the single widget I/O executor. Only the owner's rows are reusable.
    private static JSONObject lastDay;
    private static String lastDate, lastSession;
    private static long lastRead;

    JSONObject day(String day, boolean team, boolean force) throws Exception {
        String session = prefs.getString("session", "");
        long now = android.os.SystemClock.elapsedRealtime();
        if (!force && !team && !session.isEmpty() && session.equals(lastSession)
                && day.equals(lastDate) && lastDay != null && now - lastRead < 300000) {
            return lastDay;
        }
        lastDay = null;
        JSONObject result = call("sales_widget_month", new JSONObject().put("first_day", day)
                .put("last_day", day).put("p_team", team));
        prefs.edit().putBoolean("canCommon",result.optBoolean("can_common")).apply();
        String owner = prefs.getString("uid", "");
        JSONArray rows = result.getJSONArray("rows");
        if (!team && !owner.isEmpty()) {
            for (int i = 0; i < rows.length(); i++) {
                JSONObject row = rows.getJSONObject(i);
                if (row.optBoolean("common") || !owner.equals(row.optString("owner"))) return result;
            }
            lastDate = day;
            lastSession = prefs.getString("session", "");
            lastRead = android.os.SystemClock.elapsedRealtime();
            lastDay = new JSONObject().put("rows", rows).put("empty_days", result.getJSONArray("empty_days"));
        }
        return result;
    }
    void setEmpty(String day,boolean confirmed) throws Exception {
        JSONObject result=call("sales_empty_day_set",new JSONObject().put("p_day",day).put("p_confirmed",confirmed));
        if(!day.equals(result.optString("day"))||result.optBoolean("confirmed")!=confirmed)throw new java.io.IOException("Unverified write");
    }
    void refreshVisible() throws Exception {
        refresh(MonthWidget.shown(this),prefs.getBoolean("team",false));
        prefs.edit().putString("state","").apply();
    }

    private void fetchMonth(JSONObject session, YearMonth month, boolean team) throws Exception {
        String token = session.getString("access");
        JSONObject payload = month(token, month, team);
        JSONArray events = payload.getJSONArray("rows");
        boolean sunday = prefs.getBoolean("sunday", false);
        // Store only displayable widget fields inside the Android Keystore-encrypted month cache.
        JSONArray safe = new JSONArray();
        for (int i = 0; i < events.length(); i++) {
            JSONObject event = events.getJSONObject(i);
            if ("취소".equals(event.optString("status")) || "연기".equals(event.optString("status"))) continue;
            String kind = event.optString("kind");
            if (!java.util.Arrays.asList("TA", "AP", "PC", "CS", "청약", "제안", "활동", "상담", "휴무").contains(kind)) kind = "기타";
            safe.put(new JSONObject().put("day", event.getString("day")).put("kind", kind)
                .put("title",event.isNull("title") ? kind : event.optString("title", kind)).put("start",event.isNull("start_time")?"":event.optString("start_time")).put("common",event.optBoolean("common")).put("done", "완료".equals(event.optString("status")))
                .put("personal", !event.optBoolean("common") && (session.getString("uid").equals(event.optString("owner")) || session.getString("uid").equals(event.optString("companion")))));
        }
        SharedPreferences.Editor edit = prefs.edit();
        for (String name : prefs.getAll().keySet()) {
            if (name.startsWith("month:") && !name.startsWith("month:" + month + ":")) edit.remove(name);
        }
        edit.putBoolean("canCommon",payload.optBoolean("can_common")).putBoolean("sunday", sunday).putString(cacheKey(month, team),
            encrypt(new JSONObject().put("rows", safe).put("empty_days",payload.getJSONArray("empty_days")).put("at", System.currentTimeMillis()))).apply();
    }
}
