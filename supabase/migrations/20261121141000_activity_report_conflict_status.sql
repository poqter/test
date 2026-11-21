-- PostgREST should return a business conflict without signalling a retryable
-- database transaction. Direct SQL callers retain their exception contract.
do $migration$
declare
  before text := pg_get_functiondef('private.sales_save_report(date,text,jsonb,integer,integer,boolean)'::regprocedure);
  edited text := before;
  msg text;
  original text;
begin
  foreach msg in array array['다른 화면에서 기록이 변경됐습니다. 최신 기록을 확인해 주세요','다른 화면에서 수정 초안이 변경됐습니다. 최신 기록을 확인해 주세요'] loop
    original := format('raise exception %L using errcode=''40001'';',msg);
    if strpos(edited,original)=0 then raise exception 'Unexpected report conflict implementation'; end if;
    edited := replace(edited,original,format(
      'if current_setting(''request.method'',true) = ''POST'' then perform set_config(''response.status'',''409'',true); return jsonb_build_object(''code'',''40001'',''message'',%L); end if; %s',msg,original));
  end loop;
  execute edited;
end $migration$;
