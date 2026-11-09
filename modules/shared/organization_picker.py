"""Account affiliation follows organization ancestry; it never grants permissions."""
from __future__ import annotations
import streamlit as st


def active_units(rows):
    return {str(r['id']): r for r in rows if r.get('is_active', True)}


def organization_path(uid, rows):
    units=active_units(rows);parts=[];seen=set()
    while uid in units and uid not in seen:
        seen.add(uid);row=units[uid];parts.append(row['name']);uid=str(row.get('parent_id') or '')
    return ' → '.join(reversed(parts))


def valid_affiliation(position, uid, rows):
    units=active_units(rows);row=units.get(str(uid))
    if not row:return False
    if position=='chief_representative':return row.get('code')=='HWARANG' and row.get('unit_type')=='root'
    if position=='division_head':return row.get('unit_type')=='head_unit' and row.get('code') in ('DONGVAN_HQ','VISION_HQ','BISANG_HQ')
    return row.get('unit_type') in ('branch','team')


def render_affiliation(rows, positions, profile, key):
    units=active_units(rows)
    codes=[r['code'] for r in positions if r.get('is_active',True)]
    labels={r['code']:r['display_name'] for r in positions}
    current_pos=profile.get('position_code');current=str(profile.get('organization_unit_id') or '')
    position=st.selectbox('직책',codes,index=codes.index(current_pos) if current_pos in codes else None,
                          format_func=lambda c:labels[c],key=key+'_position',placeholder='직책 선택')
    uid=None
    heads=sorted((r for r in units.values() if r.get('unit_type')=='head_unit'),key=lambda r:(r.get('sort_order',0),r['name']))
    ancestor=current;seen=set()
    while ancestor in units and units[ancestor].get('unit_type') not in ('head_unit','root') and ancestor not in seen:
        seen.add(ancestor);ancestor=str(units[ancestor].get('parent_id') or '')
    if position=='chief_representative':
        uid=next((u for u,r in units.items() if r.get('code')=='HWARANG' and r.get('unit_type')=='root'),None)
        st.text_input('소속',value='화랑',disabled=True,key=key+'_root')
        st.caption('총괄대표는 회사 전체 조직인 화랑에 소속됩니다.')
    elif position:
        if position=='division_head':heads=[r for r in heads if valid_affiliation(position,r['id'],rows)]
        ids=[str(r['id']) for r in heads]
        head=st.selectbox('상위 조직',ids,index=ids.index(ancestor) if ancestor in ids else None,
                          format_func=lambda u:units[u]['name'],key=key+'_head_'+position,placeholder='본부·직할 선택')
        if position=='division_head':
            uid=head;st.caption('본부장은 선택한 본부 자체에 소속됩니다.')
        elif head:
            children=sorted((r for r in units.values() if str(r.get('parent_id'))==head),key=lambda r:(r.get('sort_order',0),r['name']))
            ids=[str(r['id']) for r in children if r.get('unit_type') in ('branch','team')]
            uid=st.selectbox('직할·지점',ids,index=ids.index(current) if current in ids else None,
                             format_func=lambda u:units[u]['name'],key=key+'_unit_'+head+'_'+position,placeholder='직할·지점 선택')
    if uid:st.caption('선택한 소속: '+organization_path(uid,rows))
    st.caption('소속·직책 변경은 아래 저장 버튼을 눌러야 반영되며, 시스템 권한은 자동 변경되지 않습니다.')
    return position,uid


def manager_candidates(rows, uid, member, position):
    return {r['id']:r for r in rows if r.get('is_active',True) and r['id']!=member
            and r.get('organization_unit_id')==uid and r.get('position_code')==position}


def render_managers(auth, actor, member, unit, key):
    """Optional reporting lines are separate from the account's own position."""
    auth._require_super_admin(actor)
    people=auth._request('GET','/rest/v1/profiles',admin=True,params={'organization_unit_id':'eq.'+str(unit),'is_active':'eq.true','position_code':'in.(team_leader,deputy_branch_manager)','select':'id,display_name,login_id,position_code,organization_unit_id,is_active'}) if unit else []
    chosen={}
    for field,table,position,label in (
        ('deputy_manager','sales_deputy_assignments','deputy_branch_manager','담당 부지점장 · 선택'),
        ('team_leader','sales_team_assignments','team_leader','담당 팀장 · 선택')):
        rows=auth._request('GET','/rest/v1/'+table,admin=True,params={'member':'eq.'+member,'select':'leader','limit':'1'})
        old=rows[0]['leader'] if rows else None
        candidates=manager_candidates(people,unit,member,position)
        choices=[None,*sorted(candidates,key=lambda u:(candidates[u]['display_name'],u))]
        chosen[field]=st.selectbox(label,choices,index=choices.index(old) if old in choices else 0,
            format_func=lambda u:'미지정' if u is None else candidates[u]['display_name']+' · '+str(candidates[u].get('login_id') or ''),key=key+'_'+field+'_'+str(unit))
        if old and old not in candidates:st.caption('기존 담당자의 소속·직책이 변경되었습니다. 저장 시 선택한 담당자로 갱신됩니다.')
    st.caption('동일한 직할·지점의 담당자만 선택할 수 있으며, 담당자가 없으면 미지정으로 두세요.')
    return chosen
