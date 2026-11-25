-- Normalize new widget events before the existing overlap check.
do $migration$
declare
  original text := pg_get_functiondef('public.sales_widget_save(uuid,integer,jsonb,boolean)'::regprocedure);
  marker text := ' if s is not null and coalesce(old.status,';
  addition text := $body$
 if old.id is null and p_revision is null and k <> '휴무' and pending and s is null and e is null then
   declare parts text[];
   begin
     parts := regexp_match(t, '^([01]?[0-9]|2[0-3]):([0-5][0-9])[[:blank:]]+([^[:blank:]~～∼–—-].*)$');
     if parts is not null then
       s := make_time(parts[1]::integer, parts[2]::integer, 0);
       t := parts[3];
       pending := false;
     end if;
   end;
 end if;
$body$;
begin
  if array_length(string_to_array(original, marker),1) <> 2 then
    raise exception 'Unexpected widget save function layout';
  end if;
  execute replace(original, marker, addition || marker);
end
$migration$;
