-- Approved production fix: the trusted CBT server invokes the existing scope predicate.
-- No grants to anon or authenticated; existing organization visibility rules stay intact.
GRANT EXECUTE ON FUNCTION private.can_user_view(uuid, uuid) TO service_role;
