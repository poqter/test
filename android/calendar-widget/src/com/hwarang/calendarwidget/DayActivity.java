package com.hwarang.calendarwidget;

import android.app.Activity;
import android.app.AlertDialog;
import android.app.DatePickerDialog;
import android.os.Bundle;
import android.text.InputType;
import android.widget.*;
import java.time.LocalDate;
import java.time.ZoneId;
import java.util.UUID;
import org.json.*;

/** Own event editor, opened directly by the widget. No browser or token-bearing URLs. */
public final class DayActivity extends Activity {
    private WidgetData data; private LinearLayout body; private TextView status;
    private String day,account; private boolean team,busy,editing; private int generation;
    private boolean confirmedEmpty, hasPersonal;
    private LinearLayout header;
    private interface Task { JSONObject run() throws Exception; }
    private interface Done { void run(JSONObject value) throws Exception; }
    @Override public void onCreate(Bundle state){
        super.onCreate(state);data=new WidgetData(this);account=data.prefs.getString("uid","");
        day=getIntent().getStringExtra("day");if(day==null)day=LocalDate.now(ZoneId.of("Asia/Seoul")).toString();
        try{LocalDate.parse(day);}catch(Exception ex){finish();return;}
        android.view.Window window=getWindow();
        int width=getResources().getDisplayMetrics().widthPixels;
        int limit=Math.round(440*getResources().getDisplayMetrics().density);
        window.setLayout(Math.min(limit,(int)(width*.92)),android.view.ViewGroup.LayoutParams.WRAP_CONTENT);
        window.setSoftInputMode(android.view.WindowManager.LayoutParams.SOFT_INPUT_ADJUST_RESIZE);
        team=getIntent().getBooleanExtra("team",false);load();
    }
    private void screen(String title){
        generation++;editing=false;ScrollView scroll=new ScrollView(this);body=new LinearLayout(this);body.setOrientation(LinearLayout.VERTICAL);
        int pad=(int)(20*getResources().getDisplayMetrics().density);body.setPadding(pad,pad,pad,pad);scroll.addView(body);setContentView(scroll);
        android.graphics.drawable.GradientDrawable card=new android.graphics.drawable.GradientDrawable();
        card.setColor(0xffffffff);card.setCornerRadius(dp(18));scroll.setBackground(card);
        getWindow().setBackgroundDrawableResource(android.R.color.transparent);
        getWindow().setLayout(Math.min(dp(480),(int)(getResources().getDisplayMetrics().widthPixels*.92)), -2);
        header=new LinearLayout(this);body.addView(header);
        TextView h=label(title,21);h.setTypeface(null,android.graphics.Typeface.BOLD);
        header.addView(h,new LinearLayout.LayoutParams(0,-2,1));
        status=label("",13);status.setTextColor(0xff475569);body.addView(status);
    }
    private int dp(int n){return Math.round(n*getResources().getDisplayMetrics().density);}
    private TextView label(String text,int size){
        TextView v=new TextView(this);v.setText(text);v.setTextSize(size);v.setTextColor(0xff142e40);return v;
    }
    private Button button(String text,Runnable action){
        Button b=new Button(this,null,android.R.attr.borderlessButtonStyle);
        b.setAllCaps(false);b.setText(text);b.setTextColor(0xff006d6d);body.addView(b);
        b.setOnClickListener(v->{if(!busy)action.run();});return b;
    }
    private void primary(Button b){
        android.graphics.drawable.GradientDrawable bg=new android.graphics.drawable.GradientDrawable();
        bg.setColor(0xff007577);bg.setCornerRadius(dp(10));b.setBackground(bg);b.setTextColor(0xffffffff);
    }
    private String dateTitle(){return LocalDate.parse(day).format(java.time.format.DateTimeFormatter.ofPattern("M월 d일 (E)",java.util.Locale.KOREAN));}
    private void headerAction(String text,String description,Runnable action){
        TextView x=label(text,23);x.setGravity(17);x.setContentDescription(description);x.setFocusable(true);
        header.addView(x,new LinearLayout.LayoutParams(dp(48),dp(48)));x.setOnClickListener(v->action.run());
    }
    private EditText field(String label,String value,int type){TextView l=new TextView(this);l.setText(label);body.addView(l);EditText e=new EditText(this);e.setContentDescription(label);e.setText(value);e.setInputType(type);body.addView(e);return e;}
    private void task(Task work,Done done,boolean write){
        if(busy)return;if(account.isEmpty()||!account.equals(data.prefs.getString("uid",""))){status.setText("설정에서 계정을 연결한 뒤 다시 열어 주세요.");return;}
        busy=true;int current=generation;TextView message=status;message.setText(write?"저장 중…":"불러오는 중…");
        WidgetData.io.execute(()->{JSONObject value=null;String error=null;
            try{value=work.run();}catch(WidgetData.HttpFailure ex){error=ex.code==401?"연결이 만료되었습니다. 설정에서 다시 연결해 주세요.":ex.code==403?"조회·수정 권한을 확인해 주세요.":ex.code==409?"일정이 변경되었습니다. 목록에서 다시 열어 주세요.":"처리하지 못했습니다. 해당 날짜의 일정·휴무와 입력 내용을 확인해 주세요.";}
            catch(Exception ex){error=write?"저장 결과를 확인하지 못했습니다. 목록에서 반영 여부를 확인해 주세요.":"연결을 확인한 뒤 다시 불러와 주세요.";}
            final JSONObject result=value;final String failure=error;
            runOnUiThread(()->{busy=false;if(isFinishing()||current!=generation)return;if(!account.equals(data.prefs.getString("uid",""))){finish();return;}
                if(failure!=null){message.setText(failure);return;}try{done.run(result);}catch(Exception ex){message.setText("결과를 표시하지 못했습니다. 목록을 다시 열어 주세요.");}
            });
        });
    }
    private void refreshWidget(){WidgetData.io.execute(()->{try{data.refreshVisible();}catch(Exception ex){data.prefs.edit().putString("state","갱신 지연 · 새로고침해 주세요").apply();}MonthWidget.paintAll(this);});}
    private void load(){ load(false); }
    private void load(boolean force){
        screen(dateTitle());headerAction("×","닫기",this::finish);
        final String selected=day;
        task(()->data.day(selected,team,force),payload->{
            JSONArray rows=payload.getJSONArray("rows"),empty=payload.getJSONArray("empty_days");boolean personal=false,confirmed=false;
            for(int i=0;i<empty.length();i++)if(selected.equals(empty.optString(i)))confirmed=true;
            java.util.List<JSONObject> visible=new java.util.ArrayList<>();
            for(int i=0;i<rows.length();i++){
                JSONObject row=rows.getJSONObject(i);
                if(!"취소".equals(row.optString("status")) && !"연기".equals(row.optString("status")))visible.add(row);
            }
            visible.sort(java.util.Comparator.comparing(r->r.isNull("start_time")?(r.optBoolean("time_pending")?"99":"00"):r.optString("start_time")));
            int common=0;
            for(JSONObject row:visible){
                boolean shared=row.optBoolean("common");
                if(shared)common++;
                if(!shared&&(account.equals(row.optString("owner"))||account.equals(row.optString("companion"))))personal=true;
                LinearLayout line=new LinearLayout(this);line.setGravity(android.view.Gravity.CENTER_VERTICAL);
                line.setMinimumHeight(dp(62));line.setPadding(0,dp(6),0,dp(6));body.addView(line);
                String clock=row.isNull("start_time")?(row.optBoolean("time_pending")?"시간 미정":"종일"):time(row,"start_time");
                line.addView(label(clock,14),new LinearLayout.LayoutParams(dp(62),-2));
                android.view.View accent=new android.view.View(this);accent.setBackgroundColor(shared?0xffaf621b:0xff008180);
                line.addView(accent,new LinearLayout.LayoutParams(dp(3),dp(34)));
                LinearLayout words=new LinearLayout(this);words.setOrientation(1);words.setPadding(dp(10),0,0,0);
                line.addView(words,new LinearLayout.LayoutParams(0,-2,1));
                words.addView(label(row.optString("title",row.optString("kind","일정")),16));
                String place=text(row,"place");words.addView(label((shared?"지점 공통 · ":"")+row.optString("kind")+(place.isEmpty()?"":" · "+place),12));
                line.addView(label("›",20));line.setFocusable(true);line.setOnClickListener(v->{if(!busy)detail(row);});
            }
            confirmedEmpty=confirmed;hasPersonal=personal;
            status.setText((team?"지점 일정 ":"내 일정 ")+(visible.size()-common)+"건"+(common>0?" · 지점 공통 "+common+"건":"")+(confirmed?" · 내 일정 없음":""));
            primary(button("＋ 일정 등록",()->editor(null)));
        },false);
    }
    private interface DateResult{void set(String value);}
    private void pick(String value,DateResult result){LocalDate d=LocalDate.parse(value);new DatePickerDialog(this,(v,y,m,n)->result.set(LocalDate.of(y,m+1,n).toString()),d.getYear(),d.getMonthValue()-1,d.getDayOfMonth()).show();}
    private void detail(JSONObject summary){
        if(!summary.optBoolean("readable",true)){new AlertDialog.Builder(this).setMessage("이 일정은 요약만 조회할 수 있습니다.").setPositiveButton("확인",null).show();return;}
        task(()->data.call("sales_calendar_detail",new JSONObject().put("p_id",summary.getString("id"))),value->{JSONObject row=value.getJSONObject("row");
            screen("일정 상세");headerAction("‹","목록으로 돌아가기",()->load());
            status.setText(row.optBoolean("common")?"지점 공통":"");
            body.addView(label(row.optString("title"),20));
            for(String[] entry:new String[][]{{"일시",row.optString("day")+"  "+(text(row,"start_time").isEmpty()?(row.optBoolean("time_pending")?"시간 미정":"종일"):time(row,"start_time"))+(text(row,"end_time").isEmpty()?"":" – "+time(row,"end_time"))},{"활동 유형",text(row,"kind")},{"장소",text(row,"place")},{"메모",text(row,"note")}}){
                if(!entry[1].isEmpty()){TextView v=label(entry[0]+"   "+entry[1],15);v.setPadding(0,dp(9),0,dp(9));body.addView(v);}
            }
            if(account.equals(row.optString("owner")))primary(button("수정",()->editor(row)));
        },false);
    }
    private String text(JSONObject row,String key){return row==null||row.isNull(key)?"":row.optString(key);}
    private String time(JSONObject row,String key){String v=text(row,key);return v.isEmpty()?"":v.substring(0,5);}
    private void editor(JSONObject row){
        screen(dateTitle()+(row==null?" · 새 일정":" · 수정"));editing=true;
        headerAction("‹","목록으로 돌아가기",this::back);
        RadioGroup modes=new RadioGroup(this);modes.setOrientation(0);
        RadioButton normal=new RadioButton(this),empty=new RadioButton(this);
        if(row==null){normal.setText("일정 입력");empty.setText("이 날 내 일정 없음");modes.addView(normal);modes.addView(empty);normal.setChecked(true);body.addView(modes);empty.setEnabled(!hasPersonal);}
        int firstField=body.getChildCount();String id=row==null?UUID.randomUUID().toString():row.optString("id");
        EditText title=field("일정명",text(row,"title"),InputType.TYPE_CLASS_TEXT);title.setFilters(new android.text.InputFilter[]{new android.text.InputFilter.LengthFilter(200)});
        String[] kinds={"미분류","TA","AP","PC","CS","청약","교육","회의","휴무","기타"};Spinner kind=new Spinner(this);kind.setContentDescription("활동 종류");kind.setAdapter(new ArrayAdapter<String>(this,android.R.layout.simple_spinner_dropdown_item,kinds));body.addView(kind);
        for(int i=0;i<kinds.length;i++)if(kinds[i].equals(text(row,"kind")))kind.setSelection(i);
        EditText place=field("장소 · 선택",text(row,"place"),InputType.TYPE_CLASS_TEXT);
        LinearLayout options=new LinearLayout(this);body.addView(options);
        CheckBox common=new CheckBox(this);common.setText("지점 공통 일정");common.setChecked(row!=null&&row.optBoolean("common"));
        CheckBox all=new CheckBox(this);all.setText("종일");all.setChecked(row!=null&&row.isNull("start_time")&&!row.optBoolean("time_pending"));options.addView(all);if(data.prefs.getBoolean("canCommon",false))options.addView(common);
        LinearLayout times=new LinearLayout(this);body.addView(times);
        EditText[] clocks=new EditText[2];int ci=0;
        for(String key:new String[]{"start_time","end_time"}){
            LinearLayout col=new LinearLayout(this);col.setOrientation(1);times.addView(col,new LinearLayout.LayoutParams(0,-2,1));
            col.addView(label(ci==0?"시작 시간":"종료 시간",13));EditText clock=new EditText(this);clock.setSingleLine();clock.setInputType(InputType.TYPE_CLASS_NUMBER);clock.setText(time(row,key));col.addView(clock);clocks[ci++]=clock;
        }
        EditText start=clocks[0],end=clocks[1];
        for(EditText input:new EditText[]{start,end}){input.setHint("예: 930 또는 1430");input.setOnFocusChangeListener((v,focus)->{if(!focus)try{input.setText(Clock.parse(input.getText().toString()));}catch(Exception ex){input.setError(ex.getMessage());}});}
        all.setOnCheckedChangeListener((v,checked)->times.setVisibility(checked?8:0));times.setVisibility(all.isChecked()?8:0);
        EditText note=field("메모 · 선택",text(row,"note"),InputType.TYPE_CLASS_TEXT|InputType.TYPE_TEXT_FLAG_MULTI_LINE);
        if(row!=null&&!text(row,"series_id").isEmpty())status.setText("이번 회차만 수정합니다.");
        Button save=button(row==null?"일정 등록":"변경 저장",()->{});
        primary(save);
        modes.setOnCheckedChangeListener((g,checkedId)->{
            boolean hide=empty.isChecked();for(int i=firstField;i<body.indexOfChild(save);i++)body.getChildAt(i).setVisibility(hide?8:0);
            if(!hide && all.isChecked())times.setVisibility(8);
            save.setText(hide?(confirmedEmpty?"일정 없음 등록 취소":"이 날 내 일정 없음으로 등록"):"일정 등록");
        });
        save.setOnClickListener(v->{if(busy)return;try{
            if(row==null&&empty.isChecked()){
                task(()->{data.setEmpty(day,!confirmedEmpty);return new JSONObject();},result->{refreshWidget();load(true);},true);return;
            }
            String k=kind.getSelectedItem().toString();boolean leave="휴무".equals(k);String s=all.isChecked()||leave?"":Clock.parse(start.getText().toString()),e=all.isChecked()||leave?"":Clock.parse(end.getText().toString());
            String name=leave?"휴무":title.getText().toString().trim();if(name.isEmpty())throw new IllegalArgumentException("일정명을 입력해 주세요.");if(!e.isEmpty()&&(s.isEmpty()||e.compareTo(s)<=0))throw new IllegalArgumentException("종료 시간은 시작 시간보다 늦어야 합니다.");
            JSONObject payload=new JSONObject().put("day",row==null?day:row.optString("day",day)).put("title",name).put("kind",k).put("start_time",s).put("end_time",e).put("time_pending",!all.isChecked()&&!leave&&s.isEmpty()).put("place",place.getText().toString()).put("note",note.getText().toString());
            if(data.prefs.getBoolean("canCommon",false))payload.put("common",common.isChecked());
            save(new JSONObject().put("p_id",id).put("p_revision",row==null?JSONObject.NULL:row.getInt("revision")).put("p_data",payload).put("p_overlap",false),save);
        }catch(Exception ex){status.setText(ex.getMessage());}});
    }
    private void save(JSONObject args,Button button){
        task(()->data.call("sales_widget_save",args),result->{
            if(result.optBoolean("overlap")){new AlertDialog.Builder(this).setMessage("기존 일정과 시간이 겹칩니다. 저장할까요?").setNegativeButton("계속 작성",null).setPositiveButton("저장",(d,w)->{try{args.put("p_overlap",true);save(args,button);}catch(Exception ex){status.setText("입력을 확인해 주세요.");}}).show();return;}
            if(!args.getString("p_id").equals(result.optString("id")))throw new IllegalStateException();button.setEnabled(false);editing=false;day=result.getString("day");refreshWidget();load(true);
        },true);
    }
    private void back(){if(busy)return;if(editing)new AlertDialog.Builder(this).setMessage("저장하지 않고 목록으로 돌아갈까요?").setNegativeButton("계속 작성",null).setPositiveButton("돌아가기",(d,w)->load()).show();else finish();}
    @Override public void onBackPressed(){back();}
}
