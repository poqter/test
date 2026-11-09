-- The header only reduces the authenticated account's normal sales scope.
-- Missing header preserves compatibility for existing non-calendar clients.
create or replace function private.sales_scope()
returns table(member uuid,label text,unit uuid,managed boolean)
language sql stable security definer set search_path='' as $$
 select * from private.sales_scope_for(auth.uid(),
   coalesce(nullif(current_setting('request.headers',true),'')::jsonb->>'x-hwarang-view-scope','all') <> 'all')
$$;
