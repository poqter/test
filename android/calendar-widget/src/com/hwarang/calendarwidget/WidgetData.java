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
import java.time.LocalDate;
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
        return (JSONObject) request(path, token, body, null);
    }

    private static Object request(String path, String token, JSONObject body, String prefer) throws Exception {
        HttpURLConnection conn = (HttpURLConnection) new URL(ROOT + path).openConnection();
        try {
            conn.setInstanceFollowRedirects(false);
            conn.setConnectTimeout(3500);
            conn.setReadTimeout(3500);
            conn.setRequestProperty("apikey", KEY);
            if (token != null) conn.setRequestProperty("Authorization", "Bearer " + token);
            if (prefer != null) conn.setRequestProperty("Prefer", prefer);
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
                String response = bytes.toString("UTF-8");
                return response.trim().isEmpty() ? new JSONObject() : new org.json.JSONTokener(response).nextValue();
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

    private JSONObject loadSession() throws Exception {
        String encrypted = prefs.getString("session", "");
        if (encrypted.isEmpty()) return null;
        return new JSONObject(decrypt(encrypted));
    }

    private String decrypt(String encrypted) throws Exception {
        String[] parts = encrypted.split(":", 2);
        Cipher cipher = Cipher.getInstance("AES/GCM/NoPadding");
        cipher.init(Cipher.DECRYPT_MODE, key(), new GCMParameterSpec(128, Base64.decode(parts[0], Base64.NO_WRAP)));
        return new String(cipher.doFinal(Base64.decode(parts[1], Base64.NO_WRAP)), StandardCharsets.UTF_8);
    }

    private String encrypt(String value) throws Exception {
        Cipher cipher = Cipher.getInstance("AES/GCM/NoPadding");
        cipher.init(Cipher.ENCRYPT_MODE, key());
        byte[] encrypted = cipher.doFinal(value.getBytes(StandardCharsets.UTF_8));
        return Base64.encodeToString(cipher.getIV(), Base64.NO_WRAP) + ":" + Base64.encodeToString(encrypted, Base64.NO_WRAP);
    }

    private JSONObject saveSession(JSONObject response, String previousUser) throws Exception {
        JSONObject user = response.optJSONObject("user");
        String uid = user == null ? previousUser : user.getString("id");
        if (uid == null || (previousUser != null && !previousUser.equals(uid))) throw new HttpFailure(401);
        JSONObject session = new JSONObject().put("uid", uid).put("access", response.getString("access_token"))
            .put("refresh", response.getString("refresh_token"))
            .put("expires", response.optLong("expires_at", System.currentTimeMillis() / 1000 + response.optLong("expires_in", 3600)));
        if (!prefs.edit().putString("uid", uid).putString("session", encrypt(session.toString())).commit())
            throw new java.io.IOException("Could not store session");
        return session;
    }

    void signIn(String email, String password) throws Exception {
        JSONObject response = request("/auth/v1/token?grant_type=password", null,
            new JSONObject().put("email", email).put("password", password));
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
        SharedPreferences.Editor edit = prefs.edit().remove("session").remove("uid").remove("member_id").remove("member_label").remove("sunday").remove("includeDone").putBoolean("team", false);
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

    boolean showsTitles() {
        String uid = prefs.getString("uid", "");
        return !uid.isEmpty() && prefs.getBoolean("show_titles:" + uid, false);
    }

    void setShowTitles(boolean enabled) {
        String uid = prefs.getString("uid", "");
        if (uid.isEmpty()) return;
        SharedPreferences.Editor edit = prefs.edit().putBoolean("show_titles:" + uid, enabled);
        if (!enabled) {
            for (String name : prefs.getAll().keySet())
                if (name.endsWith(":false:titles") && name.startsWith("month:")) edit.remove(name);
        }
        edit.apply();
    }

    JSONObject titles(YearMonth month) {
        if (!showsTitles()) return new JSONObject();
        String cached = prefs.getString(cacheKey(month, false) + ":titles", "");
        if (cached.isEmpty()) return new JSONObject();
        try { return new JSONObject(decrypt(cached)); }
        catch (Exception invalid) { return new JSONObject(); }
    }

    String member(boolean team) {
        return team ? prefs.getString("member_id", "") : "";
    }

    String memberLabel() { return prefs.getString("member_label", ""); }

    void selectMember(String member, String label) {
        SharedPreferences.Editor edit = prefs.edit().putString("member_id", member).putString("member_label", label);
        for (String name : prefs.getAll().keySet())
            if (name.startsWith("month:") && name.contains(":true:")) edit.remove(name);
        edit.apply();
    }

    private JSONObject calendarContext(JSONObject session) throws Exception {
        return request("/rest/v1/rpc/sales_calendar_context", session.getString("access"), new JSONObject());
    }

    String createEvent(String expectedUid, JSONObject draft, String acceptedOverlap) throws Exception {
        return withSession(session -> {
            String uid = session.getString("uid");
            if (!expectedUid.equals(uid)) throw new HttpFailure(403);
            String token = session.getString("access");
            JSONArray members = calendarContext(session).getJSONArray("members");
            String unit = "";
            for (int i = 0; i < members.length(); i++) {
                JSONObject row = members.getJSONObject(i);
                if (uid.equals(row.optString("member"))) { unit = row.optString("unit"); break; }
            }
            if (!validMember(unit)) throw new HttpFailure(403);

            String id = draft.getString("id");
            JSONObject event = new JSONObject(draft.toString()).put("owner", uid).put("unit", unit);
            String start = DayAgendaActivity.value(event, "start_time");
            if (!start.isEmpty()) {
                String day = event.getString("day");
                JSONArray scheduled = (JSONArray) request("/rest/v1/sales_events?select=id,start_time,end_time"
                    + "&owner=eq." + uid + "&day=eq." + day + "&status=eq.%EC%98%88%EC%A0%95"
                    + "&deleted_at=is.null&start_time=not.is.null", token, null, null);
                java.util.List<String> overlaps = new java.util.ArrayList<>();
                for (int i = 0; i < scheduled.length(); i++) {
                    JSONObject row = scheduled.getJSONObject(i);
                    if (!id.equals(row.optString("id")) && timesOverlap(start, DayAgendaActivity.value(event, "end_time"),
                            row.getString("start_time"), DayAgendaActivity.value(row, "end_time"))) {
                        overlaps.add(row.getString("id") + "/" + row.getString("start_time") + "/" + row.optString("end_time"));
                    }
                }
                java.util.Collections.sort(overlaps);
                String confirmation = draft.toString() + overlaps;
                if (!overlaps.isEmpty() && !confirmation.equals(acceptedOverlap)) return confirmation;
            }
            request("/rest/v1/sales_events?on_conflict=id", token, event, "resolution=ignore-duplicates,return=minimal");
            JSONArray saved = (JSONArray) request("/rest/v1/sales_events?id=eq." + id + "&owner=eq." + uid
                + "&deleted_at=is.null&select=id,day,title,kind,start_time,end_time,time_pending,place,note", token, null, null);
            if (saved.length() != 1) throw new java.io.IOException("Event receipt not found");
            JSONObject row = saved.getJSONObject(0);
            for (String field : new String[]{"day","title","kind","start_time","end_time","time_pending","place","note"}) {
                if (!event.optString(field).equals(row.optString(field))) throw new java.io.IOException("Event receipt differs");
            }
            return null;
        });
    }

    static boolean timesOverlap(String start, String end, String otherStart, String otherEnd) {
        java.time.LocalTime first = java.time.LocalTime.parse(start);
        java.time.LocalTime second = java.time.LocalTime.parse(otherStart);
        java.time.LocalTime firstEnd = end.isEmpty() ? first : java.time.LocalTime.parse(end);
        java.time.LocalTime secondEnd = otherEnd.isEmpty() ? second : java.time.LocalTime.parse(otherEnd);
        return first.equals(second) || (first.isBefore(secondEnd) && second.isBefore(firstEnd));
    }

    JSONArray branchMembers() throws Exception {
        return withSession(session -> calendarContext(session).getJSONArray("branch"));
    }

    boolean canGroupBranch() throws Exception {
        return withSession(session -> {
            JSONArray members = calendarContext(session).getJSONArray("members");
            String uid = session.getString("uid");
            for (int i = 0; i < members.length(); i++) {
                JSONObject row = members.getJSONObject(i);
                if (uid.equals(row.optString("member"))) return row.optBoolean("managed");
            }
            return false;
        });
    }

    static boolean validMember(String id) {
        try { return java.util.UUID.fromString(id).toString().equals(id); }
        catch (IllegalArgumentException invalid) { return false; }
    }

    String cacheKey(YearMonth month, boolean team) {
        return cacheKey(month, team, member(team));
    }

    private String cacheKey(YearMonth month, boolean team, String member) {
        return "month:" + month + ":" + team + (member.isEmpty() ? "" : ":" + member);
    }

    private static JSONArray month(String token, YearMonth month, boolean team) throws Exception {
        return calendar(token, month.atDay(1), month.atEndOfMonth(), team).getJSONArray("rows");
    }

    private static JSONObject calendar(String token, LocalDate first, LocalDate last, boolean team) throws Exception {
        return request("/rest/v1/rpc/sales_calendar_compact", token, new JSONObject()
            .put("first_day", first.toString()).put("last_day", last.toString()).put("p_team", team));
    }

    JSONObject day(LocalDate day, boolean team, String member) throws Exception {
        return withSession(session -> {
            JSONObject result = calendar(session.getString("access"), day, day, team);
            if (team && !member.isEmpty()) {
                if (findMember(result, member) == null) throw new HttpFailure(403);
                result.put("rows", memberRows(result.getJSONArray("rows"), member));
            }
            return result;
        });
    }

    private static JSONObject findMember(JSONObject payload, String member) throws Exception {
        JSONArray branch = payload.getJSONArray("branch");
        for (int i = 0; i < branch.length(); i++) {
            JSONObject item = branch.getJSONObject(i);
            if (member.equals(item.optString("member"))) return item;
        }
        return null;
    }

    private static JSONArray memberRows(JSONArray rows, String member) throws Exception {
        JSONArray filtered = new JSONArray();
        for (int i = 0; i < rows.length(); i++) {
            JSONObject event = rows.getJSONObject(i);
            if (member.equals(event.optString("owner"))) filtered.put(event);
        }
        return filtered;
    }

    void refresh(YearMonth month, boolean team) throws Exception {
        withSession(session -> {
            fetchMonth(session, month, team);
            return null;
        });
    }

    private interface SessionRequest<T> {
        T run(JSONObject session) throws Exception;
    }

    private <T> T withSession(SessionRequest<T> request) throws Exception {
        JSONObject session;
        try { session = loadSession(); }
        catch (Exception invalidStore) { throw new HttpFailure(401); }
        if (session == null) throw new HttpFailure(401);
        if (session.getLong("expires") <= System.currentTimeMillis() / 1000 + 30) session = renew(session);
        try {
            return request.run(session);
        } catch (HttpFailure failure) {
            if (failure.code != 401) throw failure;
            return request.run(renew(session));
        }
    }

    private void fetchMonth(JSONObject session, YearMonth month, boolean team) throws Exception {
        String token = session.getString("access");
        String member = member(team);
        JSONObject payload = calendar(token, month.atDay(1), month.atEndOfMonth(), team);
        JSONArray events = payload.getJSONArray("rows");
        if (!member.equals(member(team))) return;
        if (!member.isEmpty()) {
            JSONObject selected = findMember(payload, member);
            if (selected == null) {
                selectMember("", "");
                member = "";
            } else {
                prefs.edit().putString("member_label", selected.optString("label")).apply();
                events = memberRows(events, member);
            }
        }
        JSONObject user = request("/auth/v1/user", token, null);
        if (!session.getString("uid").equals(user.getString("id"))) throw new HttpFailure(401);
        JSONObject metadata = user.optJSONObject("user_metadata");
        boolean sunday = metadata != null && metadata.optInt("hwarang_calendar_month_week_start", 1) == 0;
        // Keep opted-in, readable personal titles separate from the plain calendar cache.
        boolean keepTitles = !team && showsTitles();
        JSONObject titles = new JSONObject();
        JSONArray safe = new JSONArray();
        for (int i = 0; i < events.length(); i++) {
            JSONObject event = events.getJSONObject(i);
            String kind = event.optString("kind");
            if (!java.util.Arrays.asList("TA", "AP", "PC", "CS", "청약", "휴무").contains(kind)) kind = "기타";
            JSONObject row = new JSONObject().put("day", event.getString("day")).put("kind", kind)
                .put("done", "완료".equals(event.optString("status")));
            if (!team && event.optBoolean("readable")) {
                row.put("time", DayAgendaActivity.displayTime(event));
                String title = DayAgendaActivity.value(event, "title").replaceAll("[\\r\\n]+", " ");
                if (keepTitles && !title.isEmpty()) {
                    int end = title.offsetByCodePoints(0, Math.min(96, title.codePointCount(0, title.length())));
                    titles.put(Integer.toString(i), title.substring(0, end));
                }
            }
            safe.put(row);
        }
        SharedPreferences.Editor edit = prefs.edit();
        for (String name : prefs.getAll().keySet()) {
            if (name.startsWith("month:") && !name.startsWith("month:" + month + ":")) edit.remove(name);
        }
        if (!team) {
            String titleKey = cacheKey(month, false) + ":titles";
            if (keepTitles && showsTitles() && titles.length() > 0) edit.putString(titleKey, encrypt(titles.toString()));
            else edit.remove(titleKey);
        }
        edit.putBoolean("sunday", sunday).putString(cacheKey(month, team, member),
            new JSONObject().put("rows", safe).put("at", System.currentTimeMillis()).toString()).apply();
    }
}
