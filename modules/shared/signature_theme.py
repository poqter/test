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
.hw-page-copy{min-width:0}
.hw-breadcrumb{margin-bottom:4px;letter-spacing:.045em}
.hw-page-title{font-weight:780;line-height:1.25}
.hw-page-desc{margin-top:6px;color:var(--hw-muted);font-size:16px;line-height:1.6}
.hw-section-head{margin:32px 0 14px}
.hw-section-label{color:#755727;font-size:14px;font-weight:750;letter-spacing:.05em}
.hw-section-title{margin-top:4px;font-weight:760}
.hw-section-desc{margin-top:5px;color:var(--hw-muted);font-size:15px;line-height:1.6}
.hw-guide-intro{margin-bottom:14px;color:var(--hw-ink)}
.hw-guide-label{margin:16px 0 8px;color:#755727;font-size:14px;font-weight:750}
.hw-guide-steps{display:grid;gap:8px}
.hw-guide-step{display:flex;gap:12px;padding:12px;border:1px solid var(--hw-line);border-radius:12px;background:var(--hw-bg)}
.hw-guide-number{flex:0 0 28px;height:28px;display:grid;place-items:center;border-radius:50%;background:#EAE4D8;font-size:13px;font-weight:750}
.hw-guide-copy b,.hw-guide-copy span{display:block}
.hw-guide-copy span{margin-top:2px;color:var(--hw-muted);font-size:14px;line-height:1.55}
.hw-page-footer{display:flex;justify-content:space-between;gap:16px;margin-top:40px;padding-top:16px;border-top:1px solid var(--hw-line);color:var(--hw-muted);font-size:14px}
.hw-page-footer-brand{color:var(--hw-ink);font-weight:700}
.hw-login-brand{display:flex;align-items:center;gap:12px;margin-bottom:20px}
.hw-login-brand .hw-logo{display:grid;place-items:center;width:48px;height:48px;border-radius:14px;background:var(--hw-ink);color:#D8BD88;font-size:24px;font-weight:800}
.hw-login-brand strong{display:block;font-size:20px}
.hw-login-brand small{font-size:14px;color:var(--hw-muted)}
.hw-login-hero{padding:28px 32px;margin-bottom:24px;border:1px solid var(--hw-line);border-radius:20px;background:linear-gradient(135deg,#fff,#F3EBDD)}
.hw-login-kicker,.sig-eyebrow{color:#755727;font-size:14px;font-weight:700;letter-spacing:.06em}
.hw-title-top,.hw-title-accent{display:block}
.hw-title-accent{color:#755727;font-style:normal}
.hw-login-copy p{color:var(--hw-muted)}
.hw-login-contact{display:flex;align-items:center;justify-content:space-between;gap:12px;margin-top:12px;padding:14px 16px;border:1px solid var(--hw-line);border-radius:12px;background:#fff}
.hw-login-contact a{color:#17233C;font-weight:700}
.hw-page-icon,.hw-icon{background:#F3EBDD!important;color:#17233C!important}
.hw-guide-box{background:#fff!important;border-color:#E3E6EA!important}
.sig-brand{display:flex;gap:14px;align-items:center;margin-bottom:20px}
.sig-mark{display:grid;place-items:center;background:#17233C;color:#D8BD88;border-radius:12px;width:48px;height:48px;font-size:25px;font-weight:700}
.sig-brand strong{display:block;font-size:18px;letter-spacing:.04em;color:#17233C}
.sig-brand small{font-size:14px;color:#586277}
.sig-intro{margin:4px 0 24px}
.sig-intro h1{font-size:32px!important;margin-bottom:4px!important}
.sig-intro p{color:#586277}
.sig-icon svg{width:26px;height:26px;fill:none;stroke:currentColor;stroke-width:1.7;stroke-linecap:round;stroke-linejoin:round}
.sig-icon{display:inline-grid;place-items:center;width:46px;height:46px;border-radius:12px;background:#F3EBDD;color:#17233C;margin-bottom:12px}
.sig-card-title{font-size:18px;font-weight:700;color:#17233C}
.sig-card-desc{font-size:14px;line-height:1.6;color:#586277;min-height:45px;margin:8px 0 12px}
.sig-eyebrow{color:#86662F;font-size:14px;font-weight:650;letter-spacing:.06em}
.sig-footer{border-top:1px solid #E3E6EA;padding-top:24px;margin-top:32px;font-size:14px;color:#586277}
.sig-steps{display:flex;gap:12px;margin:8px 0 20px;flex-wrap:wrap}
.sig-step{padding:8px 12px;background:#F3EBDD;color:#17233C;font-size:14px;border-radius:8px}
.ip-home-result strong,.ip-card-top strong{font-size:16px!important;color:#17233C!important}
.ip-home-phone,.ip-phone{font-size:14px!important;color:#586277!important}
.ip-home-arrow{font-size:20px!important;min-width:32px;text-align:center}
.ip-home-badge,.ip-badge{font-size:14px!important}
.ip-home-logo-box{width:40px!important;height:40px!important;flex-basis:40px!important}
.ip-home-hlab-mark{background:#17233C!important;color:#D8BD88!important}
.ip-home-result{min-height:56px!important;background:#fff!important;border-color:#E3E6EA!important}
[data-testid="stDialog"] [role="dialog"]{border-radius:20px!important;background:#fff!important}
@media(max-width:768px){
[data-testid="stMainBlockContainer"]{padding:4.7rem 16px 3rem!important}
.sig-intro h1{font-size:28px!important}
.hw-page-title,h1{font-size:25px!important}
[data-testid="stMetricValue"]{font-size:27px!important}
.stButton button,.stDownloadButton button{min-height:52px!important}
[data-testid="stMain"] [data-testid="stHorizontalBlock"]{flex-wrap:wrap!important}
[data-testid="stMain"] [data-testid="stColumn"]{min-width:min(100%,260px)!important}
.st-key-sig_home_grid [data-testid="stColumn"]{flex:1 1 100%!important;width:100%!important}
.sig-card-desc{min-height:0}
.sig-brand strong{font-size:16px}
.ip-home-phone{display:none}
.hw-page-head{gap:12px}
.hw-page-icon{flex-basis:46px;width:46px;height:46px}
.hw-page-footer,.hw-login-contact{align-items:stretch;flex-direction:column}
.hw-login-hero{padding:22px 18px}}
@media(prefers-reduced-motion:reduce){
*,*:before,*:after{transition:none!important;animation:none!important;scroll-behavior:auto!important}}/* Login and home refresh. Other tool pages retain the shared theme. */
.stApp:has(.hw-auth-bg),.stApp:has(.hw-auth-bg) [data-testid="stAppViewContainer"]{background:radial-gradient(circle at 18% 78%,#244f79 0,#112b49 33%,#071a30 77%)!important;color:#fff!important}
.stApp:has(.hw-auth-bg) [data-testid="stHeader"]{background:transparent!important}
.stApp:has(.hw-auth-bg) [data-testid="stSidebar"]{display:none!important}
.stApp:has(.hw-auth-bg) [data-testid="stMainBlockContainer"]{max-width:1080px!important;min-height:95vh;padding-top:35px!important;display:flex;flex-direction:column;justify-content:center}
.hw-auth-bg{position:fixed;left:0;bottom:-185px;width:530px;height:530px;border-radius:50%;border:1px solid #67b7dc24;box-shadow:0 0 0 80px #7cc6e508,0 0 0 160px #7cc6e506;pointer-events:none}
.hw-auth-brand{display:flex;align-items:center;gap:9px;color:#fff;font-size:18px;font-weight:600;margin:0 0 65px}
.hw-auth-brand span{display:inline-grid;place-items:center;width:34px;height:34px;border-radius:9px;background:#b9e6e8;color:#0d324e;font-size:23px;font-weight:800}
.hw-auth-copy{padding:25px 0}
.hw-auth-copy>span{font-size:12px;letter-spacing:.19em;font-weight:750;color:#79d3d7}
.hw-auth-copy h1{color:#fff!important;font-size:clamp(32px,4vw,48px)!important;line-height:1.28;letter-spacing:-.06em;margin:15px 0 12px}
.hw-auth-copy p{color:#b7cada!important;font-size:16px}
.hw-auth-copy i{display:block;height:3px;width:54px;background:#78cfcd;border-radius:3px;margin-top:31px}
[class*="st-key-hw_auth_card"]{background:#f8fbff;border-radius:17px;padding:32px!important;box-shadow:0 28px 70px #0010206b;color:#172d45}
[class*="st-key-hw_auth_card"] h2{color:#172d45!important;font-size:25px!important;margin:8px 0}
[class*="st-key-hw_auth_card"] label p{font-size:14px!important;color:#33485e!important}
[class*="st-key-hw_auth_card"] button[kind="primary"]{background:#143c61!important;border-color:#143c61!important}
[class*="st-key-hw_auth_card"] [data-testid="stForm"]{border:0!important;padding:0!important}
.hw-auth-card-heading small{color:#248195;letter-spacing:.14em;font-size:12px;font-weight:700}
.hw-auth-card-heading p{color:#6d7d8e!important;margin:0 0 20px}
.hw-auth-footer{font-size:12px;color:#b5cbdc;margin-top:70px}
[data-testid="stSidebar"]{background:#fff!important;border-right:1px solid #e8eef2!important}
.sig-brand{gap:10px;margin-bottom:25px}
.sig-mark{width:36px;height:36px;border-radius:9px;background:#143c61;color:#d6f3f2;font-size:21px}
.sig-brand strong{font-size:16px;letter-spacing:0}
.sig-brand small{font-size:13px}
@media(max-width:768px){
.hw-auth-brand{margin-bottom:15px}
.hw-auth-footer{margin-top:25px}
.hw-auth-copy{padding:5px 0}}/* Refinement from the deployed screen: subtle central light well and unified home surfaces. */
.stApp:has(.hw-auth-bg) [data-testid="stAppViewContainer"]:before{content:"";position:fixed;left:50%;top:50%;width:min(1190px,88vw);height:min(680px,79vh);transform:translate(-50%,-50%);border-radius:50%;background:radial-gradient(ellipse at 50% 48%,#5b84a61b 0%,#2d5a7920 43%,#0c243900 73%);box-shadow:inset 0 0 95px #9ac9d009,0 0 120px #85b3d010;pointer-events:none;z-index:0}
.stApp:has(.hw-auth-bg) [data-testid="stMainBlockContainer"]{position:relative;z-index:1}
[class*="st-key-hw_portal_search"]{background:#fff;border:1px solid #dce8ef;border-radius:17px;padding:22px 25px!important;margin:23px 0 18px;box-shadow:0 10px 30px #173a5510}
.hw-portal-heading span{display:block;font-size:11px;letter-spacing:.14em;color:#2e8c98;font-weight:750}
.hw-portal-heading strong{display:block;color:#183c55;font-size:20px;margin:5px 0}
.hw-portal-heading p{margin:0 0 15px;color:#637b8d;font-size:14px!important}
[class*="st-key-hw_portal_search"] input{background:#f7fbfd!important;border:1px solid #cddde7!important}
[class*="st-key-hw_portal_search"] .ip-home-result{background:#f8fbfd!important;border-color:#dce8ef!important}
@media(max-width:768px){
.stApp:has(.hw-auth-bg) [data-testid="stAppViewContainer"]:before{width:110vw;height:60vh}
[class*="st-key-hw_portal_search"]{padding:18px!important}}
[class*="st-key-hw_portal_search"]{margin:16px 0 0!important;padding:22px!important;background:#f8fcff!important;border:1px solid #ffffffb8!important;border-radius:17px!important;box-shadow:0 18px 38px #061b2b38!important;min-height:145px}
@media(max-width:800px){
[class*="st-key-hw_portal_search"]{margin:7px 0 0!important}}/* Login working surface: scoped to the login only. */
.stApp:has(.hw-auth-bg) [data-testid="stAppViewContainer"]:before{display:none!important}
.stApp:has(.hw-auth-bg) [data-testid="stMainBlockContainer"]{max-width:1220px!important;min-height:100svh;padding:48px 24px!important}
.st-key-hw_auth_shell{position:relative;padding:32px 36px!important;border:1px solid rgba(168,220,233,.24)!important;border-top-color:rgba(204,239,244,.38)!important;border-radius:26px!important;background:linear-gradient(125deg,rgba(63,108,144,.26),rgba(18,48,75,.62) 52%,rgba(7,26,47,.82))!important;box-shadow:0 28px 70px rgba(0,9,22,.42),0 6px 18px rgba(0,9,22,.24),inset 0 1px 0 rgba(220,249,255,.12),inset 0 -1px 0 rgba(0,8,20,.3)!important;backdrop-filter:blur(18px);-webkit-backdrop-filter:blur(18px)}
.st-key-hw_auth_shell .hw-auth-brand{margin-bottom:40px}
.st-key-hw_auth_shell .hw-auth-footer{margin-top:52px;color:#b9d0df}
.st-key-hw_auth_card [data-testid="stTextInput"] [data-baseweb="input"]{background:#edf3f8!important;border:2px solid #829caf!important;border-radius:11px!important;min-height:52px;box-shadow:inset 0 2px 4px rgba(16,45,68,.06)!important;transition:border-color .16s ease,box-shadow .16s ease}
.st-key-hw_auth_card [data-testid="stTextInput"] [data-baseweb="base-input"]{background:transparent!important}
.st-key-hw_auth_card [data-testid="stTextInput"] input{background:transparent!important;color:#142d44!important;font-size:16px!important;caret-color:#087f8c}
.st-key-hw_auth_card [data-testid="stTextInput"] input::placeholder{color:#536d83!important;opacity:1}
.st-key-hw_auth_card [data-testid="stTextInput"] [data-baseweb="input"]:hover{border-color:#456d8b!important}
.st-key-hw_auth_card [data-testid="stTextInput"] [data-baseweb="input"]:focus-within{border-color:#087f8c!important;box-shadow:0 0 0 3px rgba(8,127,140,.19)!important}
.st-key-hw_auth_card [data-testid="stTextInput"] button{color:#244d69!important;background:transparent!important}
@media(max-width:768px){
.stApp:has(.hw-auth-bg) [data-testid="stMainBlockContainer"]{padding:24px 12px!important}
.st-key-hw_auth_shell{padding:24px 18px!important;border-radius:20px!important}
.st-key-hw_auth_shell .hw-auth-brand{margin-bottom:16px}
.st-key-hw_auth_shell .hw-auth-footer{margin-top:26px}
.st-key-hw_auth_shell [data-testid="stHorizontalBlock"]{flex-wrap:wrap!important}
.st-key-hw_auth_shell [data-testid="stColumn"]{min-width:100%!important}
.st-key-hw_auth_card{padding:24px!important}}
@media(prefers-reduced-motion:reduce){
.st-key-hw_auth_card [data-testid="stTextInput"] [data-baseweb="input"]{transition:none}}/* Login feedback and password help stay inside the light login card. */
[class*="st-key-hw_auth_card"] [data-testid="stAlert"]{background:#fff0ee!important;border:1px solid #e38b80!important;border-left:5px solid #b42318!important;border-radius:10px!important;padding:14px 16px!important;color:#8c1d18!important}
[class*="st-key-hw_auth_card"] [data-testid="stAlert"] p,[class*="st-key-hw_auth_card"] [data-testid="stAlert"] [data-testid="stMarkdownContainer"]{color:#8c1d18!important;font-size:16px!important;font-weight:700!important;line-height:1.6!important}
.hw-auth-help{display:flex;flex-direction:column;gap:12px;margin-top:10px;padding-top:18px;border-top:1px solid #d3dfe8}
.hw-auth-help span{color:#425b70!important;font-size:14px!important}
.hw-auth-help a,.hw-auth-help a:visited{display:flex;align-items:center;justify-content:center;min-height:46px;padding:10px 14px;border:1px solid #e4ca00;border-radius:10px;background:#fee500!important;color:#241c00!important;text-decoration:none!important;font-size:15px!important;font-weight:750;box-sizing:border-box}
.hw-auth-help a:hover{background:#f5dc00!important;border-color:#c4ae00}
.hw-auth-help a:focus-visible{outline:3px solid #087f8c!important;outline-offset:3px}/* Border only: preserve the supplied input background, text and sizing. */
[class*="st-key-hw_auth_card"] [data-testid="stTextInputRootElement"],
[class*="st-key-hw_auth_card"] [data-testid="stTextInput"] [data-baseweb="input"]{border-width:3px!important;border-style:solid!important;border-color:#244d69!important}/* Home and sidebar: unified light workspace; login rules above are preserved. */
body:has(.hw-dashboard-marker) .stApp,body:has(.hw-dashboard-marker) [data-testid="stAppViewContainer"],body:has(.hw-dashboard-marker) [data-testid="stMain"]{background:#f5f7fa!important;color:#253247!important}
body:has(.hw-dashboard-marker) [data-testid="stHeader"]{background:#f5f7faed!important}
body:has(.hw-dashboard-marker) [data-testid="stMainBlockContainer"]{max-width:1440px!important;margin-left:auto!important;margin-right:auto!important;padding:3rem 2rem 2rem!important}
[class*="st-key-hw_dashboard"],[data-testid="stSidebar"]{font-family:'Pretendard',-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif!important}
[class*="st-key-hw_dashboard"] p,[class*="st-key-hw_dashboard"] button,[data-testid="stSidebar"] p,[data-testid="stSidebar"] button{font-family:inherit!important;letter-spacing:-.015em!important}
[class*="st-key-hw_home_welcome"]{padding:26px 28px!important;background:linear-gradient(110deg,#fff 15%,#edf4ff 100%);border:1px solid #d3e1f5;border-radius:18px;box-shadow:0 8px 26px #27476c08;margin-bottom:26px;position:relative}
[class*="st-key-hw_home_welcome"]:before{content:"";position:absolute;top:0;left:28px;width:100px;height:3px;background:linear-gradient(90deg,#3678ed,#6bc8d3);border-radius:4px}
.hw-welcome-copy>span{font-size:11px;color:#61809f;letter-spacing:.15em}
[class*="st-key-hw_dashboard"] .hw-welcome-copy h1{font-size:27px!important;font-weight:650!important;line-height:1.35!important;color:#172d46!important;margin:9px 0!important;letter-spacing:-.035em!important}
[class*="st-key-hw_dashboard"] .hw-welcome-copy p{font-size:15px!important;color:#63768b!important;font-weight:400!important;margin:0!important}
[class*="st-key-hw_dashboard"] h3{font-size:20px!important;font-weight:600!important;color:#253247!important}
.hw-dash-search-label{font-size:14px;color:#4c637d;margin-bottom:8px}
[class*="st-key-hw_dashboard"] [data-testid="stTextInputRootElement"],[class*="st-key-hw_dashboard"] [data-baseweb="input"]{background:#fff!important;border:1px solid #bed0e4!important;border-radius:10px!important}
[class*="st-key-hw_dashboard"] input{color:#253247!important;background:transparent!important;font-size:15px!important}
[class*="st-key-hw_dashboard"] input::placeholder{color:#72859b!important;opacity:1}
[class*="st-key-hw_dashboard"] [data-baseweb="base-input"]{background:transparent!important}
[class*="st-key-hw_category_navigation"]{margin:12px 0 10px!important;border-bottom:1px solid #dbe3ec;padding-bottom:12px!important}
[class*="st-key-hw_category_navigation"] button{min-height:44px!important;border-radius:9px!important;font-weight:500!important;transition:background .18s ease}
[class*="st-key-hw_category_navigation"] button p{font-size:15px!important;font-weight:550!important;color:inherit!important}
[class*="st-key-hw_category_navigation"] button[kind="primary"]{background:#e7efff!important;border-color:#a9c7ff!important;color:#215fca!important}
[class*="st-key-hw_category_navigation"] button[kind="secondary"]{background:transparent!important;border-color:transparent!important;color:#5a6c81!important}
[class*="st-key-hw_category_navigation"] button:hover{background:#eef3fa!important}
[class*="st-key-hw_dashboard"] [data-testid="stCaptionContainer"] p{color:#61758b!important;font-size:14px!important;font-weight:400!important}
[class*="st-key-hw_dash_tool_"]{background:#fff;border:1px solid #dde5ee;border-radius:16px;padding:22px!important;box-shadow:0 5px 18px #203c5b06;transition:box-shadow .18s ease,border-color .18s ease}
[class*="st-key-hw_dash_tool_"]:hover{border-color:#b8cdeb;box-shadow:0 7px 20px #224f860d}
.hw-tool-heading{display:flex;align-items:center;gap:12px;min-height:50px}
.hw-tool-symbol{display:grid;place-items:center;width:44px;height:44px;flex:0 0 44px;background:#eef4ff;border:1px solid #d4e3fc;border-radius:12px;font-size:22px;color:#386cc0}
.hw-tool-symbol.hw-icon-blue{color:#3277ee;background:#f2f6ff;border-color:#cbdcff}
.hw-tool-symbol.hw-icon-teal{color:#00a9b0;background:#effbfb;border-color:#bcebee}
.hw-tool-symbol.hw-icon-amber{color:#d99000;background:#fff9ec;border-color:#ffdda0}
.hw-tool-symbol.hw-icon-violet{color:#8053e8;background:#f7f2ff;border-color:#ded0ff}
.hw-tool-symbol svg{width:24px;height:24px;fill:none;stroke:currentColor;stroke-width:1.7;stroke-linecap:round;stroke-linejoin:round}
[class*="st-key-hw_dashboard"] .hw-tool-heading h3{font-size:18px!important;font-weight:600!important;line-height:1.45!important;margin:0!important;padding:0!important;text-align:left!important;letter-spacing:-.025em!important}
[class*="st-key-hw_dashboard"] .hw-dash-tool-desc{font-size:15px!important;font-weight:400!important;line-height:1.6!important;color:#64758a!important;min-height:72px;margin:14px 0 8px!important;text-align:left}
[class*="st-key-hw_dash_tool_"] button[kind="secondary"]{background:#fff!important;border:1px solid #cdddf2!important;color:#2b69cf!important;min-height:42px!important;border-radius:9px!important}
[class*="st-key-hw_dash_tool_"] button p{font-size:15px!important;font-weight:500!important;color:inherit!important}
[class*="st-key-hw_dash_tool_"] button:hover{background:#eff5ff!important}
.hw-dash-footer{font-size:12px;color:#7b8ba0;border-top:1px solid #e0e7ef;margin-top:26px;padding-top:17px}
[data-testid="stSidebar"]{background:#fff!important;border-right:1px solid #e0e7ef!important;color:#33475e!important}
[data-testid="stSidebar"] .sig-brand{background:linear-gradient(110deg,#fff,#f0f6ff);padding:16px;border:1px solid #dae7fb;border-radius:14px;margin-bottom:20px}
[data-testid="stSidebar"] .sig-brand strong{color:#203a56!important;font-size:17px!important}
[data-testid="stSidebar"] .sig-brand small{color:#527598!important}
[data-testid="stSidebar"] .sig-mark{background:#2d6ad5!important;color:#fff!important;box-shadow:0 5px 12px #2d6ad523}
[data-testid="stSidebar"] [data-testid="stExpander"]{background:transparent!important;border:0!important;border-radius:0!important;margin:5px 0!important}
[data-testid="stSidebar"] [data-testid="stExpander"] summary{padding:12px 6px!important;color:#344e68!important;background:transparent!important}
[data-testid="stSidebar"] [data-testid="stExpander"] summary p{font-size:15px!important;font-weight:600!important;color:#344e68!important}
[data-testid="stSidebar"] [data-testid="stExpanderDetails"]{padding:3px 4px 8px 14px!important;border-left:2px solid #e4ebf5}
[data-testid="stSidebar"] button[kind="secondary"]{background:#fff!important;color:#50647b!important;border:1px solid #e0e7ef!important;min-height:42px!important;border-radius:9px!important;text-align:left!important;justify-content:flex-start!important}
[data-testid="stSidebar"] button[kind="primary"]{background:#e9f1ff!important;border:1px solid #bbd3fb!important;color:#245fbd!important;border-left:3px solid #2d6ad5!important}
[data-testid="stSidebar"] button p{font-size:15px!important;font-weight:500!important;color:inherit!important}
[data-testid="stSidebar"] button:hover{background:#f0f5fc!important}
[data-testid="stSidebar"] [class*="st-key-hw_sidebar_quick"] button{background:#2d6ad5!important;border-color:#2d6ad5!important;color:#fff!important;margin-bottom:14px}
[data-testid="stSidebar"] [class*="st-key-hw_sidebar_quick"] button:hover{background:#225bbd!important}
[data-testid="stSidebar"] [data-testid="stCaptionContainer"] p{color:#71839a!important;font-size:12px!important}
[class*="st-key-hw_mobile_quick"]{display:none}
@media(min-width:769px) and (max-width:1100px){
[class*="st-key-hw_tool_grid"] [data-testid="stHorizontalBlock"]{flex-wrap:wrap!important}
[class*="st-key-hw_tool_grid"] [data-testid="stColumn"]{min-width:calc(50% - 12px)!important;flex:1 1 calc(50% - 12px)!important}}
@media(max-width:768px){
body:has(.hw-dashboard-marker) [data-testid="stMainBlockContainer"]{padding:4rem 1rem 2rem!important}
[class*="st-key-hw_dashboard"] [data-testid="stHorizontalBlock"]{flex-wrap:wrap!important}
[class*="st-key-hw_dashboard"] [data-testid="stColumn"]{min-width:100%!important}
[class*="st-key-hw_category_navigation"] [data-testid="stColumn"]{min-width:calc(50% - 8px)!important;flex:1 1 calc(50% - 8px)!important}
[class*="st-key-hw_home_welcome"]{padding:22px!important}
[class*="st-key-hw_mobile_quick"]{display:block}
.hw-dash-tool-desc{min-height:0!important}}
@media(prefers-reduced-motion:reduce){
[class*="st-key-hw_dash_tool_"],[class*="st-key-hw_category_navigation"] button{animation:none!important;transition:none!important;transform:none!important}}/* Final hierarchy and accessible interaction details, scoped to the workspace. */
[class*="st-key-hw_dashboard"]{--hw-home-accent:#2d6ad5}
[class*="st-key-hw_home_welcome"] [data-testid="stColumn"]{min-width:0}
[class*="st-key-hw_dashboard"] .hw-tool-heading h3{word-break:keep-all;overflow-wrap:anywhere}
.stApp [data-testid="stSidebar"] [data-testid="stExpanderDetails"] button[kind="secondary"]{border-color:transparent!important;background:transparent!important;min-height:42px!important}
.stApp [data-testid="stSidebar"] [data-testid="stExpanderDetails"] button[kind="secondary"]:hover{background:#f0f5fc!important;color:#245fbd!important}
.stApp [data-testid="stSidebar"] button[kind="primary"]:hover{background:#dce9ff!important;color:#245fbd!important}
[class*="st-key-hw_dash_tool_analyzer"]{border-color:#b5cdf0;background:linear-gradient(145deg,#f5f9ff,#fff 65%)}
[class*="st-key-hw_dash_tool_analyzer"] button[kind="secondary"]{background:#edf4ff!important;border-color:#b5cdf0!important}
[class*="st-key-hw_dash_tool_analyzer"] button[kind="secondary"]:hover{background:#dfeaff!important}
[class*="st-key-hw_dash_tool_"]:focus-within{border-color:#80a8e7}
[class*="st-key-hw_dashboard"] button:focus-visible,[data-testid="stSidebar"] button:focus-visible,[data-testid="stSidebar"] summary:focus-visible{outline:3px solid #2d6ad5!important;outline-offset:3px!important}
[class*="st-key-hw_dashboard"] [data-testid="stTextInputRootElement"]:focus-within{border-color:#2d6ad5!important;box-shadow:0 0 0 3px #2d6ad51a!important}
[class*="st-key-hw_dashboard"] [data-testid="stTextInputRootElement"] [data-baseweb="input"]{border:0!important}
@media(max-width:768px){
[class*="st-key-hw_dashboard"] .hw-welcome-copy h1{font-size:24px!important}
[class*="st-key-hw_dashboard"] .hw-dash-tool-desc{min-height:0!important}
.hw-dash-footer{line-height:1.6}}/* Stable hover states: keep contrast and geometry consistent. */
.stApp [data-testid="stSidebar"] .stButton button{transform:none!important;transition:background-color .18s ease,border-color .18s ease,color .18s ease!important}
.stApp [data-testid="stSidebar"] [class*="st-key-hw_sidebar_quick"] button,
.stApp [data-testid="stSidebar"] [class*="st-key-hw_sidebar_quick"] button:focus{background:#2d6ad5!important;border-color:#2d6ad5!important;color:#fff!important}
.stApp [data-testid="stSidebar"] [class*="st-key-hw_sidebar_quick"] button:hover{background:#245fca!important;border-color:#245fca!important;color:#fff!important}
.stApp [data-testid="stSidebar"] [class*="st-key-hw_sidebar_quick"] button:active{background:#1e51af!important;border-color:#1e51af!important;color:#fff!important}
.stApp [data-testid="stSidebar"] [class*="st-key-hw_sidebar_quick"] button p{color:#fff!important}
[class*="st-key-hw_dash_tool_"] button{transition:background-color .18s ease,border-color .18s ease!important}
[class*="st-key-hw_dash_tool_"] button:active{background:#e1ecfd!important;border-color:#a6c5f0!important}
[class*="st-key-hw_category_navigation"] button[kind="primary"]:hover{background:#dce9ff!important;border-color:#a9c7ff!important;color:#215fca!important}
@media(prefers-reduced-motion:reduce){
.stApp [data-testid="stSidebar"] .stButton button,[class*="st-key-hw_dash_tool_"] button{transition:none!important}}

/* Scoped contrast correction: do not change password input colors. */
.st-key-hw_auth_card [data-testid="stFormSubmitButton"] button{background:#173b5d!important;border:1px solid #173b5d!important;color:#fff!important;min-height:50px!important}
.st-key-hw_auth_card [data-testid="stFormSubmitButton"] button:hover{background:#214d74!important;border-color:#214d74!important}
.st-key-hw_auth_card [data-testid="stFormSubmitButton"] button p,
.st-key-hw_auth_card [data-testid="stFormSubmitButton"] button span{color:#fff!important;-webkit-text-fill-color:#fff!important;font-weight:650!important}
[data-testid="stSidebar"] [data-testid="stLayoutWrapper"]:has(>.st-key-hw_sidebar_header){position:sticky;top:0;z-index:20;background:#fff}
[data-testid="stSidebar"] .st-key-hw_sidebar_header{background:#fff;padding-bottom:10px;box-shadow:0 8px 12px #fff}
[class*="st-key-hw_dash_tool_analyzer"] button[kind="secondary"],
[class*="st-key-hw_dash_tool_analyzer"] button[kind="secondary"]:hover{background:#2867c5!important;border-color:#2867c5!important;color:#fff!important}
[class*="st-key-hw_dash_tool_analyzer"] button p{color:#fff!important}

'''

def inject_signature_styles():
    st.markdown('<style>'+CSS+'</style>',unsafe_allow_html=True)
