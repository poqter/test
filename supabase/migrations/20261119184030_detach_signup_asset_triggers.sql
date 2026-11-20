-- Stop provisioning asset accounts when a profile is created.
BEGIN;
SET LOCAL lock_timeout = '5s';

DROP TRIGGER IF EXISTS on_profile_created_ai_credit_account ON public.profiles;
DROP TRIGGER IF EXISTS on_profile_created_voice_account ON public.profiles;

COMMIT;
