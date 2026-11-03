import json
from datetime import date
from pathlib import Path
from uuid import uuid4

import streamlit as st


def contract_editor(db, day, event=None):
    with st.expander("청약·계약 입력 및 수정"):
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


def performance(db, day, members, bounds):
    st.subheader("청약·계약 실적")
    view=st.segmented_control("집계 기간",["날짜별","주간","월간"],default="월간") or "월간"
    start,end=bounds(day,view)
    member=st.selectbox("실적 조회 구성원",[None,*members],format_func=lambda u:members[u]["label"] if u else "전체 구성원")
    for label,field in [("청약 접수","day"),("계약 성립","effective")]:
        rows=db.request("GET","sales_contracts",{"and":f"({field}.gte.{start},{field}.lte.{end})","order":field+".asc"})
        rows=[r for r in rows if r["owner"] in members and (member is None or r["owner"]==member)]
        sums={p:sum(r["amount"] for r in rows if r["payment"]==p) for p in ("월납","연납","일시납")}
        st.write(f"**{label} {len(rows)}건** · "+" / ".join(f"{p} {n:,}원" for p,n in sums.items()))
        if rows:
            with st.expander(label+" 내역"):
                st.dataframe([{"구성원":members[r["owner"]]["label"],"날짜":r[field],"보험사":r["insurer"],"구분":r["category"],"납입":r["payment"],"보험료":r["amount"],"상태":r["status"]} for r in rows],hide_index=True)
