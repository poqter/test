create role anon;create role authenticated;create role service_role;
create schema auth;create schema private;
create function auth.uid() returns uuid language sql stable as $$select nullif(current_setting('request.jwt.claim.sub',true),'')::uuid$$;
create table auth.users(id uuid primary key,email text,raw_user_meta_data jsonb);
create table public.organization_units(id uuid primary key,code text,name text,parent_id uuid,unit_type text,is_active bool,sort_order int);
create table public.positions(code text primary key);
create table public.profiles(id uuid primary key,auth_email text,login_id text unique,display_name text,role text,is_active bool,organization_unit_id uuid,position_code text);
create table public.hwarang_join_codes(id uuid primary key,code_hash text,scope_organization_unit_id uuid,allow_descendants bool,is_active bool,starts_at timestamptz,expires_at timestamptz,max_uses int,used_count int);
create function private.hash_hwarang_join_code(text) returns text language sql as $$select $1$$;
create function private.is_org_descendant(uuid,uuid) returns bool language sql as $$with recursive t(id) as(select $1 union select u.id from public.organization_units u join t on u.parent_id=t.id) select exists(select 1 from t where id=$2)$$;
create table public.sales_team_assignments(member uuid primary key references profiles,leader uuid references profiles);
create table public.sales_deputy_assignments(member uuid primary key references profiles,leader uuid references profiles);
create table public.hwarang_admin_audit_log(actor_user_id uuid,target_user_id uuid,action text,details jsonb);
grant usage on schema public,auth,private to authenticated,service_role;
create function private.sales_validate_assignment() returns trigger language plpgsql security definer set search_path='' as $$
declare expected text;
begin
 perform pg_advisory_xact_lock(hashtextextended('sales-reporting-manager-assignments',0));
 expected:=case when tg_table_name='sales_team_assignments' then 'team_leader' else 'deputy_branch_manager' end;
 if new.member=new.leader or not exists(select 1 from public.profiles m join public.profiles l on m.organization_unit_id=l.organization_unit_id
 where m.id=new.member and l.id=new.leader and l.is_active and l.position_code=expected)
 then raise exception '같은 직할·지점의 활성 담당자만 지정할 수 있습니다';end if;
 if exists(with recursive edges as(select member,leader from public.sales_team_assignments union select member,leader from public.sales_deputy_assignments),
 chain(id) as(select new.leader union select e.leader from edges e join chain c on e.member=c.id)
 select 1 from chain where id=new.member) then raise exception '담당자 연결이 순환할 수 없습니다';end if;
 return new;
end $$;
revoke all on function private.sales_validate_assignment() from public,anon,authenticated;
create trigger validate_team_assignment before insert or update on public.sales_team_assignments for each row execute function private.sales_validate_assignment();
create trigger validate_deputy_assignment before insert or update on public.sales_deputy_assignments for each row execute function private.sales_validate_assignment();

