-- Affiliation catalog only: does not assign accounts or grant system permissions.
insert into public.positions(code,display_name,rank_order,is_active)
values('platform_administrator','최고관리자',700,true)
on conflict(code) do nothing;

insert into public.organization_units(code,name,unit_type,parent_id,sort_order,is_active)
select 'HWARANG_PLATFORM','화랑 플랫폼','head_unit',id,50,true
from public.organization_units where code='HWARANG'
on conflict(code) do nothing;

insert into public.organization_units(code,name,unit_type,parent_id,sort_order,is_active)
select 'PLATFORM_OPERATIONS','운영관리','branch',id,10,true
from public.organization_units where code='HWARANG_PLATFORM'
on conflict(code) do nothing;
