package com.hwarang.calendarwidget;
final class Clock {
    static String parse(String raw){
        String s=raw.trim();if(s.isEmpty())return "";
        if(s.matches("[0-9]{1,2}"))s=String.format(java.util.Locale.ROOT,"%02d:00",Integer.parseInt(s));
        else if(s.matches("[0-9]{3,4}")){int n=Integer.parseInt(s);s=String.format(java.util.Locale.ROOT,"%02d:%02d",n/100,n%100);}
        if(!s.matches("[0-9]{2}:[0-9]{2}")||Integer.parseInt(s.substring(0,2))>23||Integer.parseInt(s.substring(3))>59)throw new IllegalArgumentException("시간은 930 또는 1430처럼 입력해 주세요.");return s;
    }
}
