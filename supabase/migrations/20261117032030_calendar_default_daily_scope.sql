-- Clients without a view selection use the account's organization and position.
CREATE OR REPLACE FUNCTION private.sales_scope()
 RETURNS TABLE(member uuid, label text, unit uuid, managed boolean)
 LANGUAGE plpgsql
 STABLE SECURITY DEFINER
 SET search_path TO ''
AS $function$
declare selection jsonb; manager boolean;
begin
 selection:=private.sales_view_selection();
 if selection is null then
  return query select * from private.sales_scope_for(auth.uid(),
   coalesce(nullif(current_setting('request.headers',true),'')::jsonb->>'x-hwarang-view-scope','daily') <> 'all');
  return;
 end if;
 manager:=selection->>'position' in ('chief_representative','division_head','branch_manager','deputy_branch_manager','team_leader','platform_administrator');
 if selection->>'position' in ('chief_representative','division_head','branch_manager') then
  return query with recursive tree(id) as (
    select (selection->>'unit')::uuid union all
    select u.id from public.organization_units u join tree t on u.parent_id=t.id where u.is_active)
   select p.id,p.display_name,p.organization_unit_id,true from public.profiles p
   where p.is_active and (p.organization_unit_id in(select id from tree) or p.id=auth.uid());
 else
  return query select s.member,s.label,s.unit,s.managed from private.sales_scope_for((selection->>'subject')::uuid,true) s where s.member<>auth.uid()
   union all select p.id,p.display_name,p.organization_unit_id,manager from public.profiles p where p.id=auth.uid() and p.is_active;
 end if;
end $function$;
