"""Presentation-only Vega-Lite spec; calculation values are never mutated.

Keep the original axes/series styling without importing Altair at page startup.
The returned dictionary can be unit-tested independently of the UI renderer.
"""
from __future__ import annotations
import math
import streamlit as st


def growth_chart_spec(rows):
    values=[]
    for row in rows:
        year=float(row['경과 연수'])
        for label in ('납입 원금','총 자금'):
            amount=float(row[label])
            if not math.isfinite(year) or not math.isfinite(amount):
                raise ValueError('차트 값은 유효한 숫자여야 합니다.')
            values.append({'경과 연수':year,'구분':label,'금액':amount})
    end=max([1.0]+[row['경과 연수'] for row in values])
    return {
        'data':{'values':values},'height':200,
        'mark':{'type':'line','strokeWidth':2.5},
        'encoding':{
            'x':{'field':'경과 연수','type':'quantitative','scale':{'domain':[0,end],'nice':False},'axis':{'format':'d','tickMinStep':1}},
            'y':{'field':'금액','type':'quantitative','title':'금액 (원)','axis':{'format':',.0f'}},
            'color':{'field':'구분','type':'nominal','scale':{'domain':['납입 원금','총 자금'],'range':['#8193aa','#2468ca']},'legend':{'orient':'bottom','title':None}},
            'tooltip':[{'field':'경과 연수','type':'quantitative','format':'.0f'},
                       {'field':'구분','type':'nominal'},
                       {'field':'금액','type':'quantitative','format':',.0f'}],
        },
    }


def render_growth_chart(rows):
    if rows:
        st.vega_lite_chart(spec=growth_chart_spec(rows),width='stretch')
