revoke execute on function public.sales_widget_save(uuid,integer,jsonb,boolean), public.sales_widget_month(date,date,boolean) from public,anon;
grant execute on function public.sales_widget_save(uuid,integer,jsonb,boolean), public.sales_widget_month(date,date,boolean) to authenticated;
