import json
from datetime import date, timedelta
from pathlib import Path
from uuid import uuid4

import streamlit as st


def contract_editor(db, day, event=None):
    prefix="contract_"+str(event or day)
    # Keep unsaved widget inputs when the lazily rendered section is collapsed.
    for name in list(st.session_state):
        if name.startswith(prefix) and name.endswith(("_pick","insurer","category","payment","amount","day","status","effective","product","note")):
            st.session_state[name]=st.session_state[name]
    panel=st.expander("청약·계약 입력 및 수정",key=prefix+"panel",on_change="rerun")
    if not panel.open:return
    with panel:
        query = {"owner":"eq."+db.uid, "order":"day.desc"}
        query.update({"event":"eq."+event} if event else {"day":"eq."+str(day)})
        rows = db.request("GET", "sales_contracts", query)
        key = "contract_"+str(event or day)
        old = st.selectbox("청약 선택", [None,*rows], key=key+"_pick",
                           format_func=lambda r: f'{r["insurer"]} · {r["amount"]:,}원 · {r["status"]}' if r else "새 청약") or {}
        key += str(old.get("id","new"))+str(old.get("revision",0))
        catalog = json.loads((Path(__file__).resolve().parents[2]/"data/portal_catalog.json").read_text())
        insurers = [r["name"] for r in catalog["insurers"] if r["group"] in ("생명보험","손해보험")]
        def choice(label, options, field):
            value=old.get(field) or options[0]
            options=list(dict.fromkeys([*options,value]))
            return st.selectbox(label,options,index=options.index(value),key=key+field)
        insurer=choice("보험사",insurers,"insurer")
        category=choice("보험 구분",["인보험","일반보험","자동차보험"],"category")
        payment=choice("납입 방식",["월납","연납","일시납"],"payment")
        amount=st.number_input("보험료 · 원",min_value=0,value=old.get("amount",0),step=1000,key=key+"amount")
        received=st.date_input("접수일",date.fromisoformat(old.get("day",str(day))),key=key+"day")
        status=choice("청약 상태",["청약 접수","심사 중","성립","철회","미성립"],"status")
        effective=st.date_input("성립일",date.fromisoformat(old["effective"]) if old.get("effective") else max(received,day),min_value=received,key=key+"effective") if status=="성립" else None
        product=st.text_input("상품명 · 선택",old.get("product",""),key=key+"product")
        note=st.text_area("계약 메모 · 선택",old.get("note",""),key=key+"note")
        if st.button("청약 저장",key=key+"save"):
            if not amount:
                st.warning("보험료를 입력해 주세요.")
                return
            body=dict(day=str(received),insurer=insurer,category=category,payment=payment,amount=amount,status=status,effective=str(effective) if effective else None,product=product,note=note,event=old.get("event",event))
            if old:
                db.save("sales_contracts",body,old)
            else:
                body["id"]=st.session_state.setdefault(key+"seed",str(uuid4()))
                db.request("POST","sales_contracts",body=body,prefer="resolution=ignore-duplicates")
                del st.session_state[key+"seed"]
            st.rerun()


def performance(db, day, members, bounds, selected_member=None, key="performance", period_range=None):
    st.subheader("청약·계약 실적")
    if period_range:
        start,end=period_range
    else:
        view=st.segmented_control("집계 기간",["날짜별","주간","월간"],default="월간",key=key+"period") or "월간"
        start,end=bounds(day,view)
    member=selected_member if selected_member is not None else st.selectbox("실적 조회 구성원",[None,*members],format_func=lambda u:members[u]["label"] if u else "전체 구성원",key=key+"member")
    if member is False:member=None
    for label,field in [("청약 접수","day"),("계약 성립","effective")]:
        rows=db.request("GET","sales_contracts",{"and":f"({field}.gte.{start},{field}.lte.{end})","order":field+".asc"})
        rows=[r for r in rows if r["owner"] in members and (member is None or r["owner"]==member)]
        sums={p:sum(r["amount"] for r in rows if r["payment"]==p) for p in ("월납","연납","일시납")}
        st.write(f"**{label} {len(rows)}건** · "+" / ".join(f"{p} {n:,}원" for p,n in sums.items()))
        if rows:
            with st.expander(label+" 내역"):
                st.dataframe([{"구성원":members[r["owner"]]["label"],"날짜":r[field],"보험사":r["insurer"],"구분":r["category"],"납입":r["payment"],"보험료":r["amount"],"상태":r["status"]} for r in rows],hide_index=True)

    trend=st.expander("최근 8주 청약·성립 추이",expanded=False,key=key+"trend",on_change="rerun")
    if trend.open:
      with trend:
          unit=st.selectbox("그래프 단위",["건수","월납 보험료","연납 보험료","일시납 보험료"],key=key+"unit")
          first=day-timedelta(days=day.weekday()+49)
          weeks=[{"주 시작일":str(first+timedelta(weeks=i)),"청약":0,"성립":0} for i in range(8)]
          for label,field in [("청약","day"),("성립","effective")]:
              offset=0
              while members:
                  params={"and":f"({field}.gte.{first},{field}.lte.{day})","order":"id.asc","limit":"500","offset":str(offset),"select":"owner,"+field+",payment,amount"}
                  if member:params["owner"]="eq."+member
                  batch=db.request("GET","sales_contracts",params)
                  for row in batch:
                      if row["owner"] in members and (unit=="건수" or unit.startswith(row["payment"])):
                          weeks[(date.fromisoformat(row[field])-first).days//7][label]+=1 if unit=="건수" else row["amount"]
                  if len(batch)<500:break
                  offset+=len(batch)
          st.bar_chart(weeks,x="주 시작일",y=["청약","성립"],stack=False)

def conversions(db,start,end,members):
    st.subheader("상담 전환")
    period=db.period("sales_events",start,end,status="eq.완료")
    cohort=[e for e in period if e["owner"] in members and e["kind"] in ("TA","AP","PC")]
    tracked={e["case_id"] or e["id"] for e in cohort}
    rows=[]
    applications=[]
    ids=sorted(tracked)
    for pos in range(0,len(ids),40):
        group="in.("+",".join(ids[pos:pos+40])+")"
        rows.extend(db.request("GET","sales_events",{"case_id":group}))
    all_events={r["id"]:r for r in [*cohort,*rows]}
    pc=[r["id"] for r in all_events.values() if r["kind"]=="PC"]
    for pos in range(0,len(pc),40):
        applications.extend(db.request("GET","sales_contracts",{"event":"in.("+",".join(pc[pos:pos+40])+")"}))
    chart=[]
    for stage,target in [("TA","AP"),("AP","PC"),("PC","청약")]:
        starters=[e for e in cohort if e["kind"]==stage]
        cases={e["case_id"] or e["id"] for e in starters if e["case_id"] or any(r.get("case_id")==e["id"] for r in rows) or any(c["event"]==e["id"] for c in applications)}
        completed=set()
        planned=set()
        for e in starters:
            case=e["case_id"] or e["id"]
            following=[r for r in rows if r["case_id"]==case and r["kind"]==target and r["day"]>=e["day"]]
            if any(r["status"]=="완료" for r in following) or (target=="청약" and any(c["event"]==e["id"] for c in applications)):
                completed.add(case)
            elif any(r["status"]=="예정" for r in following):planned.add(case)
        chart.append({"단계":stage+" → "+target,"전환율(%)":round(100*len(completed)/len(cases),1) if cases else 0})
        with st.expander(f"{stage} → {target}"):
            st.caption(f"완료 {len(completed)} / {len(cases)}건 · 예정 {len(planned-completed)}건")
            for e in starters:
                case=e["case_id"] or e["id"]
                state="완료" if case in completed else "예정" if case in planned else "후속 일정 없음" if case in cases else "연결 미확인"
                st.write(e["day"],members[e["owner"]]["label"],e["title"],state)
    if cohort:st.bar_chart(chart,x="단계",y="전환율(%)",horizontal=True)
