package com.hwarang.calendarwidget;

import android.app.Activity;
import android.os.Bundle;
import android.widget.Button;
import android.widget.LinearLayout;
import android.widget.TextView;
import java.time.LocalDate;
import java.time.ZoneId;

/** Own-account confirmation, never an implicit write when opening the widget. */
public final class EmptyDayActivity extends Activity {
    private boolean busy;
    @Override public void onCreate(Bundle state) {
        super.onCreate(state);
        String day=LocalDate.now(ZoneId.of("Asia/Seoul")).toString();
        WidgetData data=new WidgetData(this);
        LinearLayout body=new LinearLayout(this); body.setOrientation(LinearLayout.VERTICAL);
        int pad=(int)(24*getResources().getDisplayMetrics().density);body.setPadding(pad,pad*2,pad,pad);
        TextView title=new TextView(this);title.setText(day+" · 오늘 일정 없음");title.setTextSize(22);body.addView(title);
        TextView status=new TextView(this);status.setText("본인의 일정 없음 상태를 등록합니다. 개인 일정이나 휴무가 있으면 등록되지 않습니다.");body.addView(status);
        Button save=new Button(this);save.setText("오늘 일정 없음 등록");body.addView(save);
        Button close=new Button(this);close.setText("닫기");close.setOnClickListener(v->finish());body.addView(close);
        setContentView(body);
        if(!data.prefs.contains("session")){status.setText("위젯 설정에서 계정을 연결해 주세요.");save.setEnabled(false);return;}
        save.setOnClickListener(v->{
            if(busy)return;
            if(!day.equals(LocalDate.now(ZoneId.of("Asia/Seoul")).toString())){status.setText("날짜가 변경되었습니다. 화면을 다시 열어 주세요.");save.setEnabled(false);return;}
            busy=true;save.setEnabled(false);status.setText("등록 중…");
            WidgetData.io.execute(()->{
                String message;
                try {data.confirmEmpty(day);message="등록했습니다. 같은 날짜에 일정이나 휴무를 추가하면 자동 해제됩니다.";}
                catch(WidgetData.HttpFailure failure){message=failure.code==401?"연결이 만료되었습니다. 설정에서 다시 연결해 주세요.":failure.code==403?"일정 등록 권한을 확인해 주세요.":"등록하지 못했습니다. 오늘 개인 일정·휴무가 있는지 확인해 주세요.";}
                catch(Exception failure){message="저장 결과를 확인하지 못했습니다. 캘린더에서 등록 상태를 확인해 주세요.";}
                MonthWidget.schedule(this);
                final String result=message;
                runOnUiThread(()->{busy=false;status.setText(result);/* Do not blindly retry uncertain writes. */});
            });
        });
    }
}
