"""Shared Signature design: restrained navy, ivory and gold, legible controls."""
import streamlit as st

CSS = '''
:root{--hw-ink:#17233C;--hw-muted:#667085;--hw-blue:#17233C;--hw-gold:#B89555;--hw-teal:#8B6B32;--hw-line:#E3E6EA;--hw-bg:#F7F6F2;--hw-soft-blue:#F3EBDD;--hw-soft-teal:#F3EBDD;--hw-surface:#fff;--hw-premium-line:#E3E6EA;--hw-success:#168A5B;--hw-warning:#C27A21;--hw-danger:#C2414B;--v2-navy:#17233C;--v2-blue:#17233C;--v2-ink:#17233C;--v2-muted:#667085;--v2-line:#E3E6EA;--v2-bg:#F7F6F2;--v2-soft:#F3EBDD;--v2-green:#168A5B}
.stApp,.stApp:has(.hw-login-hero),[data-testid="stAppViewContainer"]{background:#F7F6F2!important;color:#17233C!important}
[data-testid="stHeader"]{background:rgba(247,246,242,.95)!important}
[data-testid="stMainBlockContainer"]{max-width:1360px!important;padding:5rem 2rem 4rem!important}
[data-testid="stSidebar"]{background:#fff!important;border-right:1px solid #E3E6EA}
[data-testid="stSidebar"] .stButton button{justify-content:flex-start;min-height:48px}
[data-testid="stMain"] p,[data-testid="stMain"] li,[data-testid="stMain"] label,[data-testid="stMain"] input,[data-testid="stMain"] textarea,[data-testid="stMain"] select,[data-testid="stSidebar"] p,[data-testid="stSidebar"] label,[data-testid="stMarkdownContainer"] p{font-size:16px!important;line-height:1.65!important}
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
.hw-page-head{display:flex;align-items:flex-start;gap:16px;margin:4px 0 24px;padding-bottom:20px;border-bottom:1px solid var(--hw-line)}
.hw-page-icon{flex:0 0 52px;width:52px;height:52px;display:grid;place-items:center;border-radius:16px;font-size:18px;font-weight:750}
.hw-page-copy{min-width:0}.hw-breadcrumb{margin-bottom:4px;letter-spacing:.045em}.hw-page-title{font-weight:780;line-height:1.25}.hw-page-desc{margin-top:6px;color:var(--hw-muted);font-size:16px;line-height:1.6}
.hw-section-head{margin:32px 0 14px}.hw-section-label{color:#755727;font-size:14px;font-weight:750;letter-spacing:.05em}.hw-section-title{margin-top:4px;font-weight:760}.hw-section-desc{margin-top:5px;color:var(--hw-muted);font-size:15px;line-height:1.6}
.hw-guide-intro{margin-bottom:14px;color:var(--hw-ink)}.hw-guide-label{margin:16px 0 8px;color:#755727;font-size:14px;font-weight:750}.hw-guide-steps{display:grid;gap:8px}.hw-guide-step{display:flex;gap:12px;padding:12px;border:1px solid var(--hw-line);border-radius:12px;background:var(--hw-bg)}.hw-guide-number{flex:0 0 28px;height:28px;display:grid;place-items:center;border-radius:50%;background:#EAE4D8;font-size:13px;font-weight:750}.hw-guide-copy b,.hw-guide-copy span{display:block}.hw-guide-copy span{margin-top:2px;color:var(--hw-muted);font-size:14px;line-height:1.55}
.hw-page-footer{display:flex;justify-content:space-between;gap:16px;margin-top:40px;padding-top:16px;border-top:1px solid var(--hw-line);color:var(--hw-muted);font-size:14px}.hw-page-footer-brand{color:var(--hw-ink);font-weight:700}
.hw-login-brand{display:flex;align-items:center;gap:12px;margin-bottom:20px}.hw-login-brand .hw-logo{display:grid;place-items:center;width:48px;height:48px;border-radius:14px;background:var(--hw-ink);color:#D8BD88;font-size:24px;font-weight:800}.hw-login-brand strong{display:block;font-size:20px}.hw-login-brand small{font-size:14px;color:var(--hw-muted)}
.hw-login-hero{padding:28px 32px;margin-bottom:24px;border:1px solid var(--hw-line);border-radius:20px;background:linear-gradient(135deg,#fff,#F3EBDD)}.hw-login-kicker,.sig-eyebrow{color:#755727;font-size:14px;font-weight:700;letter-spacing:.06em}.hw-title-top,.hw-title-accent{display:block}.hw-title-accent{color:#755727;font-style:normal}.hw-login-copy p{color:var(--hw-muted)}
.hw-login-contact{display:flex;align-items:center;justify-content:space-between;gap:12px;margin-top:12px;padding:14px 16px;border:1px solid var(--hw-line);border-radius:12px;background:#fff}.hw-login-contact a{color:#17233C;font-weight:700}
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
@media(max-width:768px){[data-testid="stMainBlockContainer"]{padding:4.7rem 16px 3rem!important}.sig-intro h1{font-size:28px!important}.hw-page-title,h1{font-size:25px!important}[data-testid="stMetricValue"]{font-size:27px!important}.stButton button,.stDownloadButton button{min-height:52px!important}[data-testid="stMain"] [data-testid="stHorizontalBlock"]{flex-wrap:wrap!important}[data-testid="stMain"] [data-testid="stColumn"]{min-width:min(100%,260px)!important}.st-key-sig_home_grid [data-testid="stColumn"]{flex:1 1 100%!important;width:100%!important}.sig-card-desc{min-height:0}.sig-brand strong{font-size:16px}.ip-home-phone{display:none}.hw-page-head{gap:12px}.hw-page-icon{flex-basis:46px;width:46px;height:46px}.hw-page-footer,.hw-login-contact{align-items:stretch;flex-direction:column}.hw-login-hero{padding:22px 18px}}
@media(prefers-reduced-motion:reduce){*,*:before,*:after{transition:none!important;animation:none!important;scroll-behavior:auto!important}}
/* Login and home refresh. Other tool pages retain the shared theme. */
.stApp:has(.hw-auth-bg),.stApp:has(.hw-auth-bg) [data-testid="stAppViewContainer"]{background:radial-gradient(circle at 18% 78%,#244f79 0,#112b49 33%,#071a30 77%)!important;color:#fff!important}
.stApp:has(.hw-auth-bg) [data-testid="stHeader"]{background:transparent!important}
.stApp:has(.hw-auth-bg) [data-testid="stSidebar"]{display:none!important}
.stApp:has(.hw-auth-bg) [data-testid="stMainBlockContainer"]{max-width:1080px!important;min-height:95vh;padding-top:35px!important;display:flex;flex-direction:column;justify-content:center}
.hw-auth-bg{position:fixed;left:0;bottom:-185px;width:530px;height:530px;border-radius:50%;border:1px solid #67b7dc24;box-shadow:0 0 0 80px #7cc6e508,0 0 0 160px #7cc6e506;pointer-events:none}
.hw-auth-brand{display:flex;align-items:center;gap:9px;color:#fff;font-size:18px;font-weight:600;margin:0 0 65px}.hw-auth-brand span{display:inline-grid;place-items:center;width:34px;height:34px;border-radius:9px;background:#b9e6e8;color:#0d324e;font-size:23px;font-weight:800}
.hw-auth-copy{padding:25px 0}.hw-auth-copy>span{font-size:12px;letter-spacing:.19em;font-weight:750;color:#79d3d7}.hw-auth-copy h1{color:#fff!important;font-size:clamp(32px,4vw,48px)!important;line-height:1.28;letter-spacing:-.06em;margin:15px 0 12px}.hw-auth-copy p{color:#b7cada!important;font-size:16px}.hw-auth-copy i{display:block;height:3px;width:54px;background:#78cfcd;border-radius:3px;margin-top:31px}
[class*="st-key-hw_auth_card"]{background:#f8fbff;border-radius:17px;padding:32px!important;box-shadow:0 28px 70px #0010206b;color:#172d45}[class*="st-key-hw_auth_card"] h2{color:#172d45!important;font-size:25px!important;margin:8px 0}[class*="st-key-hw_auth_card"] label p{font-size:14px!important;color:#33485e!important}[class*="st-key-hw_auth_card"] button[kind="primary"]{background:#143c61!important;border-color:#143c61!important}[class*="st-key-hw_auth_card"] [data-testid="stForm"]{border:0!important;padding:0!important}
.hw-auth-card-heading small{color:#248195;letter-spacing:.14em;font-size:12px;font-weight:700}.hw-auth-card-heading p{color:#6d7d8e!important;margin:0 0 20px}.hw-auth-footer{font-size:12px;color:#b5cbdc;margin-top:70px}
[data-testid="stSidebar"]{background:#fff!important;border-right:1px solid #e8eef2!important}.sig-brand{gap:10px;margin-bottom:25px}.sig-mark{width:36px;height:36px;border-radius:9px;background:#143c61;color:#d6f3f2;font-size:21px}.sig-brand strong{font-size:16px;letter-spacing:0}.sig-brand small{font-size:13px}.stApp [data-testid="stSidebar"] .stButton button{transition:background .2s ease,transform .2s ease}.stApp [data-testid="stSidebar"] .stButton button:hover{background:#edf5f7!important;transform:translateX(2px)}.stApp [data-testid="stSidebar"] button[kind="primary"]{background:#eaf3f8!important;color:#123b60!important;border:0!important;border-left:3px solid #143c61!important}
.hw-new-hero{position:relative;overflow:hidden;border-radius:20px 20px 0 0;background:radial-gradient(circle at 84% 12%,#346785 0,#153e5d 28%,#0c2841 69%,#071b30 100%);color:#fff;padding:30px 38px 80px;margin-bottom:0}.hw-new-hero:after{content:"";position:absolute;right:12%;top:27%;width:125px;height:125px;border:1px solid #b5e8e453;border-radius:20px;transform:rotate(-15deg);box-shadow:-25px 18px 0 -1px #a1d7e131,-51px 36px 0 -1px #b2dfe611;pointer-events:none}.hw-new-kicker{color:#a8c9da;font-size:12px;letter-spacing:.13em;font-weight:700}.hw-new-hero-content{margin-top:45px}.hw-new-hero-content small{color:#8bd4d4;letter-spacing:.16em;font-weight:700}.hw-new-hero h1{font-size:clamp(30px,3.5vw,45px)!important;line-height:1.25;color:#fff!important;margin:12px 0!important}.hw-new-hero p{color:#bdd1de!important;font-size:16px}
.stApp:has(.hw-new-hero) [data-testid="stMainBlockContainer"]{max-width:1180px!important}.stApp:has(.hw-new-hero) [data-testid="stSegmentedControl"]{position:relative;margin-top:-55px;padding:0 22px;z-index:2}.stApp:has(.hw-new-hero) [data-testid="stSegmentedControl"] button{min-height:55px!important;padding:12px 18px;border-radius:12px 12px 0 0!important;color:#fff!important;background:#ffffff22!important;border:1px solid #ffffff30!important;transition:transform .23s ease,background .23s ease}.stApp:has(.hw-new-hero) [data-testid="stSegmentedControl"] button:hover{transform:translateY(-3px);background:#ffffff33!important}.stApp:has(.hw-new-hero) [data-testid="stSegmentedControl"] button[aria-checked="true"],.stApp:has(.hw-new-hero) [data-testid="stSegmentedControl"] button[aria-pressed="true"]{background:#f8fafc!important;color:#143852!important}
.hw-topic-heading{padding:35px 0 17px;animation:hw-rise .38s ease both}.hw-topic-heading small{color:#187d90;letter-spacing:.13em;font-size:12px;font-weight:750}.hw-topic-heading h2{font-size:27px!important;margin:7px 0;color:#182e43!important}.hw-topic-heading p{color:#71869a;font-size:15px}
[class*="st-key-hw_feature_card"]{background:linear-gradient(105deg,#e5f2f5,#d8eaf0);border-radius:19px;padding:26px!important;margin:8px 0 16px;min-height:185px;transition:transform .25s ease,box-shadow .25s ease;animation:hw-rise .38s ease both}[class*="st-key-hw_feature_card"]:hover,[class*="st-key-hw_home_card_"]:hover{transform:translateY(-5px);box-shadow:0 16px 30px #224b6124}.hw-feature-label{font-size:13px;color:#287489;font-weight:750}.hw-feature-title{font-size:29px;font-weight:750;color:#183047;margin:7px 0}.hw-feature-desc{color:#5f7888!important;font-size:15px}.stApp [class*="st-key-hw_feature_card"] button[kind="primary"]{background:#143c61!important;border-color:#143c61!important}
[class*="st-key-hw_home_card_"]{background:#fff;border:1px solid #e6edf1;border-radius:17px;padding:22px!important;min-height:180px;margin-bottom:15px;box-shadow:0 5px 15px #2a496008;transition:transform .25s ease,box-shadow .25s ease,border-color .25s ease;animation:hw-rise .38s ease both}.hw-home-card-title{font-size:20px;font-weight:700;color:#183047}.hw-home-card-desc{font-size:15px!important;color:#7890a0!important;min-height:46px}.hw-new-footer{color:#9eabb5;font-size:13px;margin:35px 0 15px}@keyframes hw-rise{from{opacity:.7;transform:translateY(10px)}to{opacity:1;transform:translateY(0)}}
@media(max-width:768px){.hw-auth-brand{margin-bottom:15px}.hw-auth-footer{margin-top:25px}.hw-auth-copy{padding:5px 0}.hw-new-hero{padding:25px 20px 75px}.hw-new-hero:after{display:none}.hw-new-hero-content{margin-top:28px}.stApp:has(.hw-new-hero) [data-testid="stSegmentedControl"]{padding:0 8px}.stApp:has(.hw-new-hero) [data-testid="stSegmentedControl"] button{padding:8px!important;font-size:12px!important}.hw-topic-heading{padding-top:26px}}
@media(prefers-reduced-motion:reduce){.hw-topic-heading,[class*="st-key-hw_feature_card"],[class*="st-key-hw_home_card_"]{animation:none!important}}
'''

def inject_signature_styles():
    st.markdown('<style>'+CSS+'</style>',unsafe_allow_html=True)
