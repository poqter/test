# Existing WORKSPACE weather reuse: local draft, operational review pending

Latest user choice: reuse the existing WORKSPACE public weather page parser. No new registration, service key or alternate-provider fallback. The official API adapter remains unused test/reference code; runtime uses weather-web.mjs exclusively.

## Scope and limits
- Source is the same weather.go.kr digital-forecast endpoint as modules/briefing/weather.py.
- Only16 existing province representative points; never infer user location or pretend district-level precision.
- Only short morning/afternoon conditions, temperatures and publication time are extracted. No rawHTML, images, air-quality third-party data or long narrative is redistributed.
- Page structure changes/invalid data => unavailable weather note; schedule stays intact.
- No explicit automated-access prohibition was identified, but page-specific redistribution permission was not verified and the general KMA copyright policy has a consultation clause for unmarked materials. User has been informed; do not describe reuse rights as conclusively approved.

## Current production state
Official-API candidate region/cache migrations and Edgev6 were deployed OFF before this provider change. Send gatefalse, weatherbudget0, usage0, newconnections0, jobs0, legacyapproved1, cron1. No keys collected or APIcalls performed. Main weatherUI has not been published.

## Further rollout, only after final review
1. Apply WEATHER_HTML_PATCH after currently deployed weather schema. It refuses transition if a selected region or cache row exists. Disables274 APIregions and enables16web-prefixed choices, no existing user selection to overwrite.
2. Deploy Edge including weather-web.mjs and updated worker/message. No KMA_SERVICE_KEY required or accessed by runtime.
3. Publish UI with explicit province representative-point notice and no inferred selection.
4. Keep dailyweatherbudget0 and Kakao gateOFF until operational review authorizes a bounded source/cache test. Confirm raw source freshness and output, not just unit fixtures.
5. When authorized, conservative request budget and15min shared cache protect source. Never fall back to another weather provider automatically.

## Personal connection cutover (not performed)
Do not disable the entire assistant automation: it also produces ChatGPT briefing. Root must pause/remove only the old Kakao-send step and preserve ChatGPT content. Block old job creation; drain in-flight jobs; neverretry uncertain sends. Then user-authorized localrevocation of oldconnection(no providerunlink/logout) and removeonlyownerexclusion enable normalnewOAuth. Old refresh can become invalid and is not rollbackbackup. Newregularsend remainsOFF until receipt/region/preferences and receivedtestverified. Explain any Kakao delivery gap before transition.
