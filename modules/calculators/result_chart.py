"""Presentation-only chart scales; underlying calculation rows are unchanged."""
import streamlit as st
import pandas as pd
import altair as alt


def render_growth_chart(rows):
    data = pd.DataFrame([{'경과 연수': float(row['경과 연수']), '구분': label, '금액': float(row[label])}
                         for row in rows for label in ('납입 원금', '총 자금')])
    end = max(1, float(data['경과 연수'].max()))
    chart = alt.Chart(data).mark_line(strokeWidth=2.5).encode(
        x=alt.X('경과 연수:Q', scale=alt.Scale(domain=[0,end],nice=False), axis=alt.Axis(format='d',tickMinStep=1)),
        y=alt.Y('금액:Q', title='금액 (원)', axis=alt.Axis(format=',.0f')),
        color=alt.Color('구분:N',scale=alt.Scale(domain=['납입 원금','총 자금'],range=['#8193aa','#2468ca']),legend=alt.Legend(orient='bottom',title=None)),
        tooltip=[alt.Tooltip('경과 연수:Q',format='.0f'), '구분:N',alt.Tooltip('금액:Q',format=',.0f')]
    ).properties(height=200)
    st.altair_chart(chart,use_container_width=True)
