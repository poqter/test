"""Shared Signature design: restrained navy, ivory and gold, legible controls."""
import streamlit as st

CSS = '''
:root{--hw-ink:#17233C;--hw-muted:#586277;--hw-blue:#17233C;--hw-teal:#8B6B32;--hw-line:#E3E6EA;--hw-bg:#F7F6F2;--hw-soft-blue:#F3EBDD;--hw-soft-teal:#F3EBDD;--hw-surface:#fff;--hw-premium-line:#E3E6EA;--v2-navy:#17233C;--v2-blue:#17233C;--v2-ink:#17233C;--v2-muted:#586277;--v2-line:#E3E6EA;--v2-bg:#F7F6F2;--v2-soft:#F3EBDD;--v2-green:#17865C}
.stApp,.stApp:has(.hw-login-hero),[data-testid="stAppViewContainer"]{background:#F7F6F2!important;color:#17233C!important}
[data-testid="stHeader"]{background:rgba(247,246,242,.95)!important}
[data-testid="stMainBlockContainer"]{max-width:1360px!important;padding:5rem 2rem 4rem!important}
[data-testid="stSidebar"]{background:#fff!important;border-right:1px solid #E3E6EA}
[data-testid="stSidebar"] .stButton button{justify-content:flex-start;min-height:48px}
p,li,label,input,textarea,select,[data-testid="stMarkdownContainer"] p{font-size:16px!important;line-height:1.65!important}
[data-testid="stCaptionContainer"] p,.hw-guide-copy span,.hw-page-footer,.hw-breadcrumb{font-size:14px!important;color:#586277!important}
h1,.hw-page-title{font-size:30px!important;letter-spacing:-.035em!important;color:#17233C!important}
h2,.hw-section-title{font-size:22px!important;color:#17233C!important}
h3{font-size:19px!important}
[data-testid="stMetricValue"]{font-size:32px!important;font-variant-numeric:tabular-nums;color:#17233C}
[data-testid="stMetric"]{background:#fff;border:1px solid #E3E6EA;border-radius:16px;padding:16px;min-width:0}
[data-testid="stWidgetLabel"] p{font-weight:600!important;color:#17233C}
table td,table th{font-size:15px!important;line-height:1.5!important}
.ip-main-portal,.ip-panel{background:#fff!important;box-shadow:none!important;border-color:#E3E6EA!important}
.ip-main-mark,.ip-main-portal>a{background:#17233C!important;color:#fff!important}
.ip-main-copy span,.ip-main-copy small,.ip-panel-head span,.ip-panel-head b,.ip-card-bottom small{font-size:14px!important;color:#586277!important}
input,textarea,[data-baseweb="select"]>div{font-size:16px!important;min-height:48px;border-radius:12px!important}
.stButton button,.stDownloadButton button,[data-testid="stFormSubmitButton"] button,[data-testid="stLinkButton"] a{min-height:48px!important;border-radius:12px!important;font-size:16px!important;font-weight:600!important;box-shadow:none!important}
button[kind="primary"],button[data-testid="stBaseButton-primary"]{background:#17233C!important;border-color:#17233C!important;color:#fff!important}
button[kind="secondary"]{border-color:#D5D8DE!important;background:#fff!important;color:#17233C!important}
button:focus-visible,input:focus-visible,textarea:focus-visible,a:focus-visible{outline:3px solid #3174D6!important;outline-offset:3px}
[data-testid="stVerticalBlockBorderWrapper"]>div{border-radius:16px!important}
[data-testid="stExpander"]{border:1px solid #E3E6EA!important;border-radius:12px!important;background:#fff}
.hw-page-header{border-bottom:1px solid #E3E6EA;padding-bottom:20px;background:transparent!important;box-shadow:none!important}
.hw-page-icon,.hw-icon{background:#F3EBDD!important;color:#17233C!important}
.hw-guide-box{background:#fff!important;border-color:#E3E6EA!important}
.sig-brand{display:flex;gap:14px;align-items:center;margin-bottom:20px}
.sig-mark{display:grid;place-items:center;background:#17233C;color:#D8BD88;border-radius:12px;width:48px;height:48px;font-size:25px;font-weight:700}
.sig-brand strong{display:block;font-size:18px;letter-spacing:.04em;color:#17233C}
.sig-brand small{font-size:14px;color:#586277}
.sig-intro{margin:4px 0 24px}.sig-intro h1{font-size:32px!important;margin-bottom:4px!important}.sig-intro p{color:#586277}
.sig-icon svg{width:26px;height:26px;fill:none;stroke:currentColor;stroke-width:1.7;stroke-linecap:round;stroke-linejoin:round}
.sig-icon{display:inline-grid;place-items:center;width:46px;height:46px;border-radius:12px;background:#F3EBDD;color:#17233C;margin-bottom:12px}
.sig-card-title{font-size:18px;font-weight:700;color:#17233C}.sig-card-desc{font-size:14px;line-height:1.6;color:#586277;min-height:45px;margin:8px 0 12px}
[class*="st-key-sig_card_"]{background:white;border-radius:16px;padding:20px!important;border:1px solid #E3E6EA;transition:border-color .16s ease}
[class*="st-key-sig_card_"]:hover{border-color:#B89555}
.sig-eyebrow{color:#86662F;font-size:14px;font-weight:650;letter-spacing:.06em}
.sig-footer{border-top:1px solid #E3E6EA;padding-top:24px;margin-top:32px;font-size:14px;color:#586277}
.sig-steps{display:flex;gap:12px;margin:8px 0 20px;flex-wrap:wrap}.sig-step{padding:8px 12px;background:#F3EBDD;color:#17233C;font-size:14px;border-radius:8px}
.ip-home-result strong,.ip-card-top strong{font-size:16px!important;color:#17233C!important}.ip-home-phone,.ip-phone{font-size:14px!important;color:#586277!important}.ip-home-arrow{font-size:20px!important;min-width:32px;text-align:center}.ip-home-badge,.ip-badge{font-size:14px!important}.ip-home-logo-box{width:40px!important;height:40px!important;flex-basis:40px!important}.ip-home-hlab-mark{background:#17233C!important;color:#D8BD88!important}
.ip-home-result{min-height:56px!important;background:#fff!important;border-color:#E3E6EA!important}
[data-testid="stDialog"] [role="dialog"]{border-radius:20px!important;background:#fff!important}
@media(max-width:768px){[data-testid="stMainBlockContainer"]{padding:4.7rem 16px 3rem!important}.sig-intro h1{font-size:28px!important}.hw-page-title,h1{font-size:25px!important}[data-testid="stMetricValue"]{font-size:27px!important}.stButton button,.stDownloadButton button{min-height:52px!important}[data-testid="stHorizontalBlock"]{flex-wrap:wrap!important}[data-testid="stColumn"]{min-width:min(100%,260px)!important}.st-key-sig_home_grid [data-testid="stColumn"]{flex:1 1 100%!important;width:100%!important}.sig-card-desc{min-height:0}.sig-brand strong{font-size:16px}.ip-home-phone{display:none}}
@media(prefers-reduced-motion:reduce){*,*:before,*:after{transition:none!important;animation:none!important;scroll-behavior:auto!important}}
'''

def inject_signature_styles():
    st.markdown('<style>'+CSS+'</style>',unsafe_allow_html=True)
