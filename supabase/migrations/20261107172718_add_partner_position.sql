-- Display ordering only; this position does not grant management permissions.
-- Existing profiles, organization assignments and audit histories are untouched.
insert into public.positions (code, display_name, rank_order, is_active)
values ('partner', '파트너', 150, true)
on conflict (code) do update
set display_name = excluded.display_name, is_active = true;
