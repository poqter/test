"""Restore manager list position after returning from a learner's detail."""
import json
import streamlit as st

def remember(restore=False):
    script='''<script>(()=>{
const w=window.parent,d=w.document,root=d.querySelector('[data-testid="stMain"]');
if(!root)return;
const selector='[class*="st-key-exam_person_"]';
if(w.__examListClick)d.removeEventListener('click',w.__examListClick,true);
w.__examListClick=e=>{if(e.target.closest(selector))w.__examListPosition=root.scrollTop;};
d.addEventListener('click',w.__examListClick,true);
if(RESTORE){let count=0;const back=()=>{if(!d.querySelector(selector)&&count++<20){w.setTimeout(back,80);return;}if(d.activeElement&&/INPUT|TEXTAREA/.test(d.activeElement.tagName))return;root.scrollTop=w.__examListPosition||0;};w.requestAnimationFrame(back);}
})();</script>'''
    st.iframe(script.replace('RESTORE',json.dumps(bool(restore))),height=0)
