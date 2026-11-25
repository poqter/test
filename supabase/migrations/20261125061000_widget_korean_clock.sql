do $migration$
declare
  original text := pg_get_functiondef('public.sales_widget_save(uuid,integer,jsonb,boolean)'::regprocedure);
  marker text := '   declare parts text[];';
  finish text := '   end;';
  first_pos integer := strpos(original, marker);
  last_pos integer;
  replacement text := $body$
   declare parts text[]; h integer; m integer; label text;
   begin
     parts := regexp_match(t, '^([01]?[0-9]|2[0-3]):([0-5][0-9])[[:blank:]]+([^[:blank:]~～∼–—-].*)$');
     if parts is not null then
       h := parts[1]::integer; m := parts[2]::integer; label := parts[3];
     else
       parts := regexp_match(t, '^(?:(오전|오후)[[:blank:]]*)?([0-9]{1,2})시(?:[[:blank:]]*(반|[0-9]{1,2}분))?[[:blank:]]+(.+)$');
       if parts is not null then
         h := parts[2]::integer;
         m := case when parts[3]='반' then 30 else coalesce(rtrim(parts[3],'분')::integer,0) end;
         if parts[1] is not null then
           if h between 1 and 12 then h := mod(h,12) + case when parts[1]='오후' then 12 else 0 end;
           else h := null; end if;
         end if;
         label := parts[4];
       end if;
     end if;
     label := btrim(label);
     if h between 0 and 23 and m between 0 and 59 and label <> '' and label !~ '^(까지|부터|쯤|경([[:space:]]|에|$)|정도|반(쯤|까지|부터|경|[[:space:]]|$)|[0-9]+분|[~～∼–—-])' then
       s := make_time(h,m,0); t := label; pending := false;
     end if;
   end;$body$;
begin
  if first_pos=0 then raise exception 'Missing clock parser'; end if;
  last_pos := strpos(substr(original,first_pos), finish);
  if last_pos=0 then raise exception 'Incomplete clock parser'; end if;
  execute overlay(original placing replacement from first_pos for last_pos-1+length(finish));
end
$migration$;
