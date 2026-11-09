-- Internal DDL event trigger: never an application RPC.
-- Keep its owner, SECURITY DEFINER body and ensure_rls event trigger intact.
-- No account, session, organization or customer data is modified.
DO $migration$
BEGIN
  -- Supabase installs this helper on some projects; older/local databases
  -- without it do not need a replacement or any new privileges.
  IF to_regprocedure('public.rls_auto_enable()') IS NOT NULL THEN
    IF NOT EXISTS (
      SELECT 1 FROM pg_proc
      WHERE oid = to_regprocedure('public.rls_auto_enable()')
        AND prorettype = 'event_trigger'::regtype
    ) THEN
      RAISE EXCEPTION 'Unexpected rls_auto_enable function type';
    END IF;
    REVOKE EXECUTE ON FUNCTION public.rls_auto_enable()
      FROM PUBLIC, anon, authenticated;
    IF has_function_privilege('anon', 'public.rls_auto_enable()', 'EXECUTE')
       OR has_function_privilege('authenticated', 'public.rls_auto_enable()', 'EXECUTE') THEN
      RAISE EXCEPTION 'Internal RLS trigger is still executable by application roles';
    END IF;
  END IF;
END
$migration$;
