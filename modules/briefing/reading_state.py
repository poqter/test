"""Keep local reading position/disclosures across native tab switches, no network."""
import streamlit as st

def install_reading_state():
    st.html('''<script>
    (()=>{
      const root=document.querySelector('.st-key-hw_briefing_center');
      if(!root||root.dataset.readingState)return;
      root.dataset.readingState='1';
      const tabs=()=>[...root.querySelectorAll('[data-baseweb="tab"]')];
      const active=()=>tabs().find(x=>x.getAttribute('aria-selected')==='true')?.textContent||'';
      const scroller=document.querySelector('[data-testid="stMain"]')||document.scrollingElement;
      const positions={};let restoring=false;
      root.addEventListener('click',ev=>{
        const target=ev.target.closest('[data-baseweb="tab"]');
        if(!target)return;
        const before=active(),after=target.textContent;
        if(before===after)return;
        positions[before]=scroller.scrollTop;
        restoring=true;
        requestAnimationFrame(()=>requestAnimationFrame(()=>{
          scroller.scrollTop=positions[after]??positions[before];restoring=false;
        }));
      },true);
      scroller.addEventListener('scroll',()=>{if(!restoring)positions[active()]=scroller.scrollTop;},{passive:true});
    })();
    </script>''',unsafe_allow_javascript=True)
