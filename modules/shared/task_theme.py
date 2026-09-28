"""Task-page theme scoped away from the approved home and sign-in screens."""
import streamlit as st
CSS = '''
body:has(.hw-task-marker) .stApp,body:has(.hw-task-marker) [data-testid="stAppViewContainer"],body:has(.hw-task-marker) [data-testid="stMain"]{background:#f5f7fa!important;color:#243247!important}
body:has(.hw-task-marker) [data-testid="stHeader"]{background:#f5f7faed!important}
body:has(.hw-task-marker) [data-testid="stMainBlockContainer"]{max-width:1480px!important;margin-inline:auto!important;padding:3.5rem 2rem 3rem!important}
.st-key-hw_task_page{--hw-ink:#243247;--hw-muted:#64748b;--hw-blue:#2d6ad5;--hw-gold:#2d6ad5;--hw-teal:#15989c;--hw-line:#dde5ef;--hw-bg:#f5f7fa;--hw-soft-blue:#eef4ff;--hw-soft-teal:#effafa;font-family:'Pretendard',sans-serif!important}
.st-key-hw_task_page p,.st-key-hw_task_page input,.st-key-hw_task_page textarea,.st-key-hw_task_page button,.st-key-hw_task_page label{font-family:inherit!important;letter-spacing:-.015em}
.st-key-hw_task_page p,.st-key-hw_task_page li,.st-key-hw_task_page label{font-size:15px!important;line-height:1.65!important}
.st-key-hw_task_page h1,.st-key-hw_task_page .hw-page-title{font-size:28px!important;font-weight:700!important;line-height:1.35;color:#20334d!important}
.st-key-hw_task_page h2{font-size:23px!important;font-weight:650!important}
.st-key-hw_task_page h3,.st-key-hw_task_page .hw-section-title{font-size:19px!important;font-weight:600!important}
.st-key-hw_task_page .hw-page-head{border:0;padding:8px 0 20px;margin:12px 0 8px;align-items:center}
.st-key-hw_task_page .hw-page-icon{width:48px;height:48px;flex-basis:48px;background:#eef4ff!important;color:#2d6ad5!important;border:1px solid #d2e2fb;border-radius:14px;font-size:16px}
.st-key-hw_task_page .hw-page-icon svg{width:25px;height:25px;fill:none;stroke:currentColor;stroke-width:1.8;stroke-linecap:round;stroke-linejoin:round}
.st-key-hw_task_page .hw-breadcrumb{font-size:12px!important;letter-spacing:.02em;color:#76849a!important;margin-bottom:6px}
.st-key-hw_task_page .hw-page-desc{font-size:15px!important;color:#64748b!important;line-height:1.6;margin-top:8px}
.st-key-hw_task_page [class*="st-key-hw_surface_"]{background:#fff;border:1px solid #e0e7ef;border-radius:18px;padding:24px!important;box-shadow:0 4px 16px #19365704;margin-bottom:8px;min-width:0}
.st-key-hw_task_page [class*="st-key-hw_surface_"]>[data-testid="stVerticalBlock"]{gap:1rem}
.st-key-hw_task_page .hw-section-head{margin:14px 0 8px}
.st-key-hw_task_page .hw-section-label,.st-key-hw_task_page .hw-guide-label{color:#2d6ad5!important;font-size:12px!important;font-weight:650!important}
.st-key-hw_task_page [data-testid="stCaptionContainer"] p{font-size:13px!important;color:#66788e!important}
.st-key-hw_task_page [data-testid="stWidgetLabel"] p{color:#344760!important;font-weight:550!important;font-size:14px!important}
.st-key-hw_task_page [data-testid="stTextInputRootElement"],.st-key-hw_task_page [data-baseweb="input"],.st-key-hw_task_page [data-baseweb="textarea"],.st-key-hw_task_page [data-baseweb="select"]>div{background:#fbfcfe!important;border:1px solid #cdd8e6!important;border-radius:10px!important}
.st-key-hw_task_page [data-testid="stTextInputRootElement"] [data-baseweb="input"]{border:0!important}
.st-key-hw_task_page input,.st-key-hw_task_page textarea{color:#25364c!important;background:transparent!important;font-size:15px!important}
.st-key-hw_task_page input::placeholder,.st-key-hw_task_page textarea::placeholder{color:#7b8b9f!important;opacity:1}
.st-key-hw_task_page [data-baseweb="input"]:focus-within,.st-key-hw_task_page [data-baseweb="textarea"]:focus-within{border-color:#2d6ad5!important;box-shadow:0 0 0 3px #2d6ad515!important}
.st-key-hw_task_page [data-testid="stForm"]{border:0!important;padding:0!important}
.st-key-hw_task_page button[kind="primary"],.st-key-hw_task_page [data-testid="stFormSubmitButton"] button{background:#2d6ad5!important;border:1px solid #2d6ad5!important;color:white!important}
.st-key-hw_task_page button[kind="primary"]:hover,.st-key-hw_task_page [data-testid="stFormSubmitButton"] button:hover{background:#245fc5!important;border-color:#245fc5!important}
.st-key-hw_task_page .stButton button,.st-key-hw_task_page .stDownloadButton button,.st-key-hw_task_page [data-testid="stFormSubmitButton"] button{border-radius:10px!important;min-height:44px!important;transform:none!important;transition:background-color .16s ease,border-color .16s ease!important}
.st-key-hw_task_page button p{color:inherit!important;font-weight:550!important}
.st-key-hw_task_page button[kind="secondary"]{color:#36577e!important;background:#fff!important;border:1px solid #cedbeb!important}
.st-key-hw_task_page button[kind="secondary"]:hover{background:#f0f5fd!important;border-color:#a4c1e9!important}
.st-key-hw_task_page button:disabled{opacity:.48!important;cursor:not-allowed}
.st-key-hw_task_page button:focus-visible,.st-key-hw_task_page a:focus-visible{outline:3px solid #2d6ad5!important;outline-offset:3px}
.st-key-hw_task_page [data-testid="stFileUploaderDropzone"]{background:#f7faff!important;border:1.5px dashed #a9c3e9!important;border-radius:14px!important;padding:20px!important}
.st-key-hw_task_page [data-testid="stFileUploaderDropzone"]:hover{border-color:#2d6ad5!important}
.st-key-hw_task_page [data-testid="stMetric"]{background:#f7faff!important;border:1px solid #dce7f6!important;border-radius:12px!important;padding:16px!important}
.st-key-hw_task_page [data-testid="stMetricValue"]{font-size:clamp(20px,2.2vw,29px)!important;color:#203c62!important;font-weight:650!important;overflow-wrap:anywhere}
.st-key-hw_task_page [data-testid="stExpander"]{background:#fff!important;border:1px solid #e0e7ef!important;border-radius:12px!important}
.st-key-hw_task_page [data-testid="stExpander"] summary{padding:12px 14px!important}
.st-key-hw_task_page [data-baseweb="tab-list"]{gap:6px;border-bottom:1px solid #e1e8f1;padding-bottom:4px;overflow-x:auto}
.st-key-hw_task_page [data-baseweb="tab"]{background:transparent!important;border-radius:8px!important;padding:10px 14px!important;color:#61738c!important;white-space:nowrap}
.st-key-hw_task_page [data-baseweb="tab"][aria-selected="true"]{background:#edf4ff!important;color:#245fc5!important}
.st-key-hw_task_page [data-baseweb="tab-highlight"]{background:#2d6ad5!important;height:2px}
.st-key-hw_task_page [data-testid="stDataFrame"],.st-key-hw_task_page [data-testid="stDataEditor"]{border:1px solid #e0e7ef;border-radius:12px;overflow:hidden}
.st-key-hw_task_page [data-testid="stAlert"]{border-radius:12px!important}
.st-key-hw_task_page .hw-guide-step,.st-key-hw_task_page .hw-guide-box{background:#f7faff!important;border-color:#dce7f6!important}
.st-key-hw_task_page .hw-guide-number{background:#e7f0ff!important;color:#2d6ad5!important}
.st-key-hw_task_page .hw-page-footer{margin-top:24px;font-size:12px!important;color:#7d8ba0!important}
.st-key-hw_task_toolbar{padding:12px 16px!important;background:#fff;border:1px solid #e0e7ef;border-radius:14px}
.st-key-hw_task_toolbar [data-testid="stColumn"]{min-width:0}
@media(max-width:1100px){.st-key-hw_task_page [class*="st-key-hw_split_"]>[data-testid="stHorizontalBlock"]{flex-direction:column!important}.st-key-hw_task_page [class*="st-key-hw_split_"]>[data-testid="stHorizontalBlock"]>[data-testid="stColumn"]{width:100%!important;flex:1 1 100%!important;min-width:100%!important}}
@media(max-width:768px){body:has(.hw-task-marker) [data-testid="stMainBlockContainer"]{padding:4rem 1rem 2rem!important}.st-key-hw_task_page [class*="st-key-hw_surface_"]{padding:18px!important;border-radius:14px}.st-key-hw_task_page .hw-page-title{font-size:24px!important}.st-key-hw_task_page [data-testid="stHorizontalBlock"]{flex-wrap:wrap!important}.st-key-hw_task_page [data-testid="stColumn"]{min-width:100%!important}.st-key-hw_task_page .hw-page-head{gap:12px}.st-key-hw_task_page [data-testid="stMetricValue"]{font-size:25px!important}}
@media(prefers-reduced-motion:reduce){.st-key-hw_task_page *{transition:none!important;animation:none!important}}
.st-key-hw_task_page{--hw-navy:#203b5c;--hw-blue-soft:#eef4ff;--hw-gold-deep:#15989c;--hw-gold-soft:#effafa}
.st-key-hw_task_page .rn-dot.fixed{background:#15989c!important}
.st-key-hw_task_page .rn-fixed-block{background:linear-gradient(160deg,#d1f0ed,#87ceca)!important;color:#174b50!important;box-shadow:none!important}
.st-key-hw_task_page [style*="background-color: #fff8e1"]{background-color:#f0f8fb!important;border-color:#a9cddd!important}
.st-key-hw_task_page [style*="background-color: #f3ecff"]{background-color:#f3f6fc!important;border-color:#c5d4eb!important}

/* Task-only compact chrome; home and sign-in keep their approved appearance. */
.st-key-hw_task_page .st-key-hw_task_toolbar{padding:8px 12px!important;border-radius:10px!important;margin-bottom:6px!important}
.st-key-hw_task_page .st-key-hw_task_toolbar [data-testid="stVerticalBlock"]{gap:.25rem!important}
.st-key-hw_task_page .st-key-hw_task_toolbar button{min-height:38px!important}
.st-key-hw_task_page [data-testid="stCaptionContainer"] p{color:#566b84!important;font-size:13px!important;opacity:1!important}
.st-key-hw_task_page [data-testid="stTextArea"] textarea{border:1px solid #ccd7e5!important;border-radius:10px!important}
/* UI audit: real Streamlit 1.64 input elements and compact task hierarchy. */
body:has(.hw-task-marker):not(:has(.hw-calculator-only)) [data-testid="stMainBlockContainer"]{padding-top:1.25rem!important}
.st-key-hw_task_page .hw-page-head{margin:4px 0 12px!important;padding:4px 0 8px!important}
.st-key-hw_task_page .st-key-hw_task_toolbar{background:transparent!important;border:0!important;padding:0!important;margin:0!important}
.st-key-hw_task_page [data-testid="stNumberInputContainer"],
.st-key-hw_task_page [data-testid="stTextInputRootElement"],
.st-key-hw_task_page [data-testid="stTextArea"] textarea,
.st-key-hw_task_page [data-baseweb="select"]>div,
.st-key-hw_task_page [data-testid="stSelectbox"] [role="group"]:has(>[role="combobox"]){
border:1.5px solid #8ea3ba!important;background:#fff!important;border-radius:9px!important;color:#18334f!important;box-shadow:none!important}
.st-key-hw_task_page [data-testid="stNumberInputContainer"]:focus-within,
.st-key-hw_task_page [data-testid="stTextInputRootElement"]:focus-within,
.st-key-hw_task_page [data-testid="stTextArea"] textarea:focus,
.st-key-hw_task_page [data-baseweb="select"]:focus-within>div{border-color:#2867c5!important;box-shadow:0 0 0 3px #2867c51c!important}
.st-key-hw_task_page input,.st-key-hw_task_page textarea{color:#18334f!important;-webkit-text-fill-color:#18334f!important;caret-color:#2867c5!important}
.st-key-hw_task_page [data-testid="stCaptionContainer"] p,.st-key-hw_task_page .hw-page-desc{color:#52657d!important;opacity:1!important}
.st-key-hw_task_page [class*="st-key-hw_surface_"]{padding:20px!important;margin-bottom:4px!important}
.st-key-hw_task_page [class*="st-key-hw_compact_"]{padding:12px 0!important}
.st-key-hw_task_page .hw-section-head{margin:4px 0 10px!important}
.st-key-hw_task_page .hw-calc-panel,.st-key-hw_task_page .hw-input-panel{background:#f4f7fc!important}
.st-key-hw_task_page .st-key-rm_live_summary h4{font-size:17px!important;line-height:1.5!important;word-break:keep-all;overflow-wrap:anywhere}
.st-key-hw_task_page .st-key-rm_live_summary{padding:18px!important}
.st-key-hw_task_page [class*="st-key-hw_calc_"] [data-testid="stVerticalBlockBorderWrapper"]{background:#fff!important;border-color:#d3deeb!important}
.st-key-hw_task_page [class*="_hero_result"] [data-testid="stMetric"]{background:#eaf2ff!important;border:1px solid #bfd3ef!important}
.st-key-hw_task_page [class*="_hero_result"] [data-testid="stMetricValue"]{font-size:30px!important}
.st-key-hw_task_page [class*="_support_result"] [data-testid="stMetric"]{padding:10px 14px!important}
.st-key-hw_task_page [class*="_support_result"] [data-testid="stMetricValue"]{font-size:21px!important}
.st-key-jc_categories{padding:4px 0 8px!important;margin-bottom:0!important}
.st-key-jc_purposes{gap:6px!important}
.st-key-hw_task_page [data-testid="stFileUploaderDropzone"]{background:#f4f8fd!important;border:1.5px dashed #91a9c4!important;border-radius:12px!important;padding:14px!important}
[data-testid="stSidebar"] .st-key-hw_sidebar_header{position:sticky;top:0;z-index:20;background:#fff;padding-bottom:10px;box-shadow:0 8px 12px #fff}
[data-testid="stSidebar"] .sig-brand{margin-bottom:8px!important;padding:12px!important}
[data-testid="stSidebar"] [data-testid="stExpander"]{margin-bottom:4px!important}
[data-testid="stSidebar"] [data-testid="stExpander"] button{min-height:38px!important;padding:6px 12px!important;justify-content:flex-start!important}
[data-testid="stSidebar"] [data-testid="stVerticalBlock"]{gap:.55rem!important}
[class*="st-key-hw_dash_tool_analyzer"]{background:linear-gradient(145deg,#eaf2ff,#f8fbff)!important;border:1.5px solid #91b2e4!important}
[class*="st-key-hw_dash_tool_analyzer"] button{background:#2d6ad5!important;color:#fff!important;border-color:#2d6ad5!important}
@media(max-width:768px){body:has(.hw-task-marker):not(:has(.hw-calculator-only)) [data-testid="stMainBlockContainer"]{padding-top:3rem!important}.st-key-hw_task_page [class*="st-key-hw_surface_"]{padding:16px!important}.st-key-hw_task_page [class*="_hero_result"] [data-testid="stMetricValue"]{font-size:26px!important}}

/* September UI review: stable outer controls and result hierarchy. */
.st-key-hw_task_page [data-testid="stSelectbox"] input[role="combobox"]{border:0!important;border-radius:0!important;box-shadow:none!important;outline:none!important;min-width:0!important;background:transparent!important}
.st-key-hw_task_page [data-testid="stSelectbox"] [role="group"]:has(>[role="combobox"]):focus-within{border-color:#2867c5!important;box-shadow:0 0 0 3px #2867c51c!important}
.st-key-hw_task_page [data-testid="stSelectbox"] [role="group"]>button{border:0!important;background:transparent!important;min-width:40px!important;border-radius:0!important}
.st-key-hw_task_page [class*="st-key-hw_calc_input_"],.st-key-hw_task_page [class*="st-key-hw_calc_result_"]{background:#fff!important;border-radius:14px!important;padding:20px!important;min-width:0;scroll-margin-top:24px}
.st-key-hw_task_page [class*="_hero_result"] [data-testid="stMetricValue"],
.st-key-hw_task_page [class*="_hero_result"] [data-testid="stMetricValue"] *{font-size:clamp(26px,2.7vw,36px)!important;line-height:1.3!important;font-weight:750!important;color:#163e71!important;white-space:normal!important;overflow-wrap:anywhere}
.st-key-hw_task_page [class*="_support_result"] [data-testid="stMetricValue"],
.st-key-hw_task_page [class*="_support_result"] [data-testid="stMetricValue"] *{font-size:22px!important;line-height:1.4!important;font-weight:650!important;white-space:normal!important;overflow-wrap:anywhere}
.st-key-hw_task_page [class*="st-key-hw_confirm_"]{background:#f0f6ff!important;border:1px solid #bed0eb!important;border-radius:12px!important;padding:14px!important}
.st-key-hw_task_page [data-testid="stWidgetLabel"] p{overflow-wrap:anywhere;white-space:normal!important}
@media(max-width:768px){
.st-key-hw_task_page [class*="st-key-hw_calc_input_"],.st-key-hw_task_page [class*="st-key-hw_calc_result_"]{padding:14px!important}
.st-key-hw_task_page [data-testid="stMetricValue"] *{white-space:normal!important;overflow-wrap:anywhere}
.st-key-hw_task_page [class*="st-key-jc_actions_"] button{white-space:normal!important;min-height:44px!important}
.st-key-hw_task_page [data-testid="stNumberInput"] input{min-width:0!important}
}


/* Compact Streamlit chrome. Keep the sidebar reopen control usable. */
[data-testid="stToolbar"], [data-testid="stMainMenu"], .stAppDeployButton {display:none!important}
[data-testid="stHeader"]{height:0!important;min-height:0!important;background:transparent!important;pointer-events:none}
[data-testid="stHeader"] button,[data-testid="stSidebarCollapsedControl"],[data-testid="stExpandSidebarButton"],
[data-testid="stSidebarCollapsedControl"] button {pointer-events:auto!important}
[data-testid="stSidebarCollapsedControl"],[data-testid="stExpandSidebarButton"]{position:fixed!important;top:8px!important;left:8px!important;z-index:1001}
body:has(.hw-dashboard-marker) [data-testid="stMainBlockContainer"],
body:has(.hw-task-marker):not(:has(.hw-calculator-only)) [data-testid="stMainBlockContainer"]{padding-top:1rem!important}
.st-key-hw_home_welcome{padding:16px 22px!important;margin-bottom:4px!important}
.st-key-hw_dashboard .hw-welcome-copy h1{font-size:24px!important;margin:5px 0!important}
.st-key-hw_dashboard [class*="st-key-hw_dash_tool_"]{padding:18px!important}
.st-key-hw_dashboard .hw-dash-tool-desc{min-height:48px!important;margin:10px 0 6px!important}
/* Same step navigation across question, comparison and claim documents. */
[class*="st-key-hw_steps_"] [role="radiogroup"]{gap:8px!important;flex-wrap:wrap}
[class*="st-key-hw_steps_"] [data-testid="stRadio"] label[data-baseweb="radio"]{border:1px solid #d6e0ed;border-radius:10px;padding:7px 12px!important;background:#fff;min-height:42px}
[class*="st-key-hw_steps_"] label:has(input:checked){background:#edf4ff!important;border-color:#87afe9!important}
/* A document checkbox stays next to its summary, including on narrow screens. */
.st-key-hw_task_page [class*="st-key-cg_document_row_"] [data-testid="stHorizontalBlock"]{flex-wrap:nowrap!important;gap:8px!important;align-items:center!important}
.st-key-hw_task_page [class*="st-key-cg_document_row_"] [data-testid="stColumn"]{min-width:0!important}
.st-key-hw_task_page [class*="st-key-cg_document_row_"] [data-testid="stColumn"]:first-child{width:28px!important;flex:0 0 28px!important}
.st-key-hw_task_page [class*="st-key-cg_document_row_"] [data-testid="stColumn"]:last-child{width:auto!important;flex:1 1 0!important}
.st-key-hw_task_page [class*="st-key-cg_document_row_"] [data-testid="stExpander"] summary{padding:8px 10px!important;min-height:44px}
.st-key-hw_task_page [class*="st-key-cg_document_row_"] [data-testid="stExpander"] summary p{font-size:14px!important;line-height:1.5!important}
@media(max-width:768px){
body:has(.hw-dashboard-marker) [data-testid="stMainBlockContainer"],
body:has(.hw-task-marker):not(:has(.hw-calculator-only)) [data-testid="stMainBlockContainer"]{padding-top:3.25rem!important}
.st-key-hw_home_welcome{padding:14px!important}
}
/* The sidebar has its own header spacer, independent of the main toolbar. */
[data-testid="stSidebar"] [data-testid="stSidebarHeader"]{
    height:0!important;min-height:0!important;padding:0!important;margin:0!important;
    position:relative;overflow:visible!important;
}
[data-testid="stSidebar"] [data-testid="stSidebarHeader"] button{
    position:absolute!important;top:3px!important;right:12px!important;
    min-height:28px!important;height:28px!important;z-index:30;
}
[data-testid="stSidebar"] [data-testid="stSidebarUserContent"]{padding-top:2rem!important}
'''

def inject_task_styles():
    st.html('<style>'+CSS+'</style>')
