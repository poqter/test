-- GitHub's regular briefing calendar uses KST weekdays. The existing
-- 21:xx–23:xx UTC slots belong to the following Korean business morning.
-- Keep all weekday recovery and response-collection opportunities.
do $migration$
declare
    target record;
begin
    if to_regclass('cron.job') is null then return; end if;
    select jobid, schedule into target from cron.job
    where jobname = 'hwarang-briefing-watchdog';
    if not found then return; end if;
    if target.schedule = '2,12,22,32,42,52 21,22,23 * * 0-4' then return; end if;
    if target.schedule <> '2,12,22,32,42,52 21,22,23 * * *' then
        raise exception 'Unexpected briefing watchdog schedule: %', target.schedule;
    end if;
    perform cron.alter_job(target.jobid, schedule := '2,12,22,32,42,52 21,22,23 * * 0-4');
end;
$migration$;
