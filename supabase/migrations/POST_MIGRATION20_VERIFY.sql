-- Read-only verification. No keys/passwords/tokens or full news are selected.
select to_regclass('public.hwarang_account_security') as password_epoch,
 to_regclass('public.hwarang_account_recovery_audit') as recovery_audit,
 to_regclass('public.hwarang_briefing_daily_runs') as daily_runs,
 to_regclass('public.hwarang_briefing_daily_budget') as daily_budget,
 to_regclass('public.hwarang_briefing_public_shares') as customer_shares;
select tgname,tgenabled from pg_trigger where tgname='hwarang_credentials_changed';
select profile_code,is_enabled,run_mode from public.hwarang_briefing_profiles order by profile_code;
select briefing_date,group_code,status,attempts,updated_at from public.hwarang_briefing_daily_runs order by briefing_date desc limit 12;
select briefing_date,web_requests,analysis_requests,search_actions from public.hwarang_briefing_daily_budget order by briefing_date desc limit 7;
select b.profile_code,b.briefing_date,r.publication_status,r.validation_status,r.coverage_status,
 r.external_share_allowed,r.external_qa_passed,s.qa_payload->>'public_body_ready' as public_body_ready,
 s.content_payload->'market_metrics'->'missing' as missing_market_metrics
from public.hwarang_briefings b join public.hwarang_briefing_revisions r on r.briefing_id=b.id
left join public.hwarang_briefing_snapshots s on s.revision_id=r.id
order by b.briefing_date desc,r.revision_no desc limit 12;
