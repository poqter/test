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
