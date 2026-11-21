package com.hwarang.calendarwidget;
public final class ClockTest {
 public static void main(String[] args){
  if(!Clock.edit("14",false).equals("14:") || !Clock.edit("14",true).equals("14") || !Clock.edit("1430",false).equals("14:30"))throw new AssertionError();
  String[][] valid={{"93:0","09:30"},{"14:","14:00"},{"930","09:30"},{"1430","14:30"},{"9","09:00"},{"0","00:00"},{"2359","23:59"},{"09:30","09:30"},{"",""}};
  for(String[] pair:valid)if(!pair[1].equals(Clock.parse(pair[0])))throw new AssertionError(pair[0]);
  for(String bad:new String[]{"2400","1260","-1","12345","12:999","abc"}){boolean rejected=false;try{Clock.parse(bad);}catch(IllegalArgumentException e){rejected=true;}if(!rejected)throw new AssertionError(bad);}
  System.out.println("PASS numeric clock normalization and invalid times");
 }
}
