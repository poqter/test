create table public.sales_contracts(
 id uuid primary key,owner uuid not null default auth.uid() references public.profiles,
 event uuid references public.sales_events, day date not null, insurer text not null check(length(insurer)>0),
 category text not null check(category in ('인보험','일반보험','자동차보험')), payment text not null check(payment in ('월납','연납','일시납')),
 amount bigint not null check(amount>0),product text not null default '',note text not null default '',
 status text not null check(status in ('청약 접수','심사 중','성립','철회','미성립')),effective date,revision integer not null default 1,
 check((status='성립')=(effective is not null)),check(effective>=day));
alter table public.sales_contracts enable row level security;
revoke all on public.sales_contracts from public,anon,authenticated;
grant select,insert,update on public.sales_contracts to authenticated;
create index sales_contract_day on public.sales_contracts(owner,day);
create policy contracts_read on public.sales_contracts for select to authenticated using(owner in(select member from private.sales_scope()));
create policy contracts_add on public.sales_contracts for insert to authenticated with check(owner=auth.uid() and private.sales_enabled() and (event is null or exists(select from public.sales_events e where e.id=event and e.owner=auth.uid())));
create policy contracts_change on public.sales_contracts for update to authenticated using(owner=auth.uid() and private.sales_enabled()) with check(owner=auth.uid() and (event is null or exists(select from public.sales_events e where e.id=event and e.owner=auth.uid())));
create trigger contract_revision before update on public.sales_contracts for each row execute function private.sales_version();
