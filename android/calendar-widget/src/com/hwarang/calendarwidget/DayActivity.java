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
    private interface Task { JSONObject run() throws Exception; }
    private interface Done { void run(JSONObject value) throws Exception; }
    @Override public void onCreate(Bundle state){
        super.onCreate(state);data=new WidgetData(this);account=data.prefs.getString("uid","");
        day=getIntent().getStringExtra("day");if(day==null)day=LocalDate.now(ZoneId.of("Asia/Seoul")).toString();
        try{LocalDate.parse(day);}catch(Exception ex){finish();return;}
        team=getIntent().getBooleanExtra("team",false);load();
    }
    private void screen(String title){
        generation++;editing=false;ScrollView scroll=new ScrollView(this);body=new LinearLayout(this);body.setOrientation(LinearLayout.VERTICAL);
        int pad=(int)(20*getResources().getDisplayMetrics().density);body.setPadding(pad,pad*2,pad,pad);scroll.addView(body);setContentView(scroll);
        TextView h=new TextView(this);h.setText(title);h.setTextSize(22);body.addView(h);status=new TextView(this);status.setTextSize(15);body.addView(status);
    }
    private Button button(String label,Runnable action){Button b=new Button(this);b.setText(label);body.addView(b);b.setOnClickListener(v->{if(!busy)action.run();});return b;}
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
    private void load(){
        screen(day+(team?" · 지점 일정":" · 내 일정"));
        button("날짜 선택",()->pick(day,d->{day=d;load();}));button("새 일정 등록",()->editor(null));button("다시 불러오기",this::load);button("닫기",this::finish);
        final String selected=day;
        task(()->data.day(selected,team),payload->{
            JSONArray rows=payload.getJSONArray("rows"),empty=payload.getJSONArray("empty_days");boolean personal=false,confirmed=false;
            for(int i=0;i<empty.length();i++)if(selected.equals(empty.optString(i)))confirmed=true;
            for(int i=0;i<rows.length();i++){
                JSONObject row=rows.getJSONObject(i);String state=row.optString("status");if("취소".equals(state)||"연기".equals(state))continue;
                if(!row.optBoolean("common")&&(account.equals(row.optString("owner"))||account.equals(row.optString("companion"))))personal=true;
                String clock=row.isNull("start_time")?(row.optBoolean("time_pending")?"시간 미정":"종일"):row.optString("start_time").substring(0,5);
                String title=row.optString("title",row.optString("kind","일정"));button(clock+"  "+title+" · "+state,()->detail(row));
            }
            status.setText(personal?"제목을 누르면 상세 내용을 확인할 수 있습니다.":confirmed?"내 일정 없음 등록됨":"내 일정 미등록");
            final boolean was=confirmed;
            if(!personal)button(was?"일정 없음 등록 취소":"이 날짜 일정 없음 등록",()->task(()->{data.setEmpty(selected,!was);return new JSONObject();},v->{refreshWidget();load();},true));
        },false);
    }
    private interface DateResult{void set(String value);}
    private void pick(String value,DateResult result){LocalDate d=LocalDate.parse(value);new DatePickerDialog(this,(v,y,m,n)->result.set(LocalDate.of(y,m+1,n).toString()),d.getYear(),d.getMonthValue()-1,d.getDayOfMonth()).show();}
    private void detail(JSONObject summary){
        if(!summary.optBoolean("readable",true)){new AlertDialog.Builder(this).setMessage("이 일정은 요약만 조회할 수 있습니다.").setPositiveButton("확인",null).show();return;}
        task(()->data.call("sales_calendar_detail",new JSONObject().put("p_id",summary.getString("id"))),value->{JSONObject row=value.getJSONObject("row");
            if(account.equals(row.optString("owner")))editor(row);else new AlertDialog.Builder(this).setTitle(row.optString("title")).setMessage(row.optString("place")+"\n"+row.optString("note")).setPositiveButton("닫기",null).show();},false);
    }
    private String text(JSONObject row,String key){return row==null||row.isNull(key)?"":row.optString(key);}
    private String time(JSONObject row,String key){String v=text(row,key);return v.isEmpty()?"":v.substring(0,5);}
    private void editor(JSONObject row){
        screen(row==null?"새 일정":"일정 수정");editing=true;String id=row==null?UUID.randomUUID().toString():row.optString("id");
        EditText title=field("일정명",text(row,"title"),InputType.TYPE_CLASS_TEXT);title.setFilters(new android.text.InputFilter[]{new android.text.InputFilter.LengthFilter(200)});
        EditText date=field("날짜",row==null?day:text(row,"day"),InputType.TYPE_CLASS_DATETIME);date.setFocusable(false);date.setOnClickListener(v->{if(!busy)pick(date.getText().toString(),date::setText);});
        String[] kinds={"미분류","TA","AP","PC","CS","청약","교육","회의","휴무","기타"};Spinner kind=new Spinner(this);kind.setContentDescription("활동 종류");kind.setAdapter(new ArrayAdapter<String>(this,android.R.layout.simple_spinner_dropdown_item,kinds));body.addView(kind);
        for(int i=0;i<kinds.length;i++)if(kinds[i].equals(text(row,"kind")))kind.setSelection(i);
        CheckBox all=new CheckBox(this);all.setText("종일");all.setChecked(row!=null&&row.isNull("start_time")&&!row.optBoolean("time_pending"));body.addView(all);
        EditText start=field("시작 시간 · 선택",time(row,"start_time"),InputType.TYPE_CLASS_NUMBER),end=field("종료 시간 · 선택",time(row,"end_time"),InputType.TYPE_CLASS_NUMBER);
        for(EditText input:new EditText[]{start,end}){input.setHint("예: 930 또는 1430");input.setOnFocusChangeListener((v,focus)->{if(!focus)try{input.setText(Clock.parse(input.getText().toString()));}catch(Exception ex){input.setError(ex.getMessage());}});}
        all.setOnCheckedChangeListener((v,checked)->{start.setEnabled(!checked);end.setEnabled(!checked);});start.setEnabled(!all.isChecked());end.setEnabled(!all.isChecked());
        EditText place=field("장소 · 선택",text(row,"place"),InputType.TYPE_CLASS_TEXT),note=field("메모 · 선택",text(row,"note"),InputType.TYPE_CLASS_TEXT|InputType.TYPE_TEXT_FLAG_MULTI_LINE);
        if(row!=null&&!text(row,"series_id").isEmpty())status.setText("이번 회차만 수정합니다.");
        Button save=button(row==null?"일정 등록":"변경 저장",()->{});
        save.setOnClickListener(v->{if(busy)return;try{
            String k=kind.getSelectedItem().toString();boolean leave="휴무".equals(k);String s=all.isChecked()||leave?"":Clock.parse(start.getText().toString()),e=all.isChecked()||leave?"":Clock.parse(end.getText().toString());
            String name=leave?"휴무":title.getText().toString().trim();if(name.isEmpty())throw new IllegalArgumentException("일정명을 입력해 주세요.");if(!e.isEmpty()&&(s.isEmpty()||e.compareTo(s)<=0))throw new IllegalArgumentException("종료 시간은 시작 시간보다 늦어야 합니다.");
            JSONObject payload=new JSONObject().put("day",date.getText().toString()).put("title",name).put("kind",k).put("start_time",s).put("end_time",e).put("time_pending",!all.isChecked()&&!leave&&s.isEmpty()).put("place",place.getText().toString()).put("note",note.getText().toString());
            save(new JSONObject().put("p_id",id).put("p_revision",row==null?JSONObject.NULL:row.getInt("revision")).put("p_data",payload).put("p_overlap",false),save);
        }catch(Exception ex){status.setText(ex.getMessage());}});button("목록으로 돌아가기",this::back);
    }
    private void save(JSONObject args,Button button){
        task(()->data.call("sales_widget_save",args),result->{
            if(result.optBoolean("overlap")){new AlertDialog.Builder(this).setMessage("기존 일정과 시간이 겹칩니다. 저장할까요?").setNegativeButton("계속 작성",null).setPositiveButton("저장",(d,w)->{try{args.put("p_overlap",true);save(args,button);}catch(Exception ex){status.setText("입력을 확인해 주세요.");}}).show();return;}
            if(!args.getString("p_id").equals(result.optString("id")))throw new IllegalStateException();button.setEnabled(false);editing=false;day=result.getString("day");refreshWidget();load();
        },true);
    }
    private void back(){if(busy)return;if(editing)new AlertDialog.Builder(this).setMessage("저장하지 않고 목록으로 돌아갈까요?").setNegativeButton("계속 작성",null).setPositiveButton("돌아가기",(d,w)->load()).show();else finish();}
    @Override public void onBackPressed(){back();}
}
