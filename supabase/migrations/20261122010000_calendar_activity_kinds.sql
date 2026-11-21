do $migration$
declare
  definition text := pg_get_functiondef('public.sales_widget_save(uuid,integer,jsonb,boolean)'::regprocedure);
  old_kinds text := '''미분류'',''TA'',''AP'',''PC'',''CS'',''청약'',''교육'',''회의'',''휴무'',''기타''';
begin
  if strpos(definition, old_kinds) = 0 then
    raise exception 'Unexpected widget kind validation';
  end if;
  execute replace(definition, old_kinds, old_kinds || ',''상담'',''활동'',''제안''');
end
$migration$;
