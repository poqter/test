# Self-service affiliation and reporting managers

- Signup preserves join-code organization scope and accepts only FP, partner, team leader, deputy branch manager, branch manager, division head.
- These requested positions apply immediately; management visibility follows the existing organization/position rules. System role remains user. Platform and chief representative cannot self-register.
- Existing active organizations only; division heads choose an approved headquarters. Other positions choose a branch/direct unit. No organization creation.
- Any position can select an active team leader and deputy in the same unit, or leave either unspecified. Self and cycle assignments are rejected.
- My account changes only the caller's reporting links, immediately. Existing records are not reassigned. Current reporting links control manager visibility, including historical records, and support-request candidates.
- Signup reference data is service-only after join-code validation. Self APIs derive identity from auth.uid(), never a caller-supplied user ID. All input is revalidated at write time.
- Existing six profiles and two reporting links were preserved during migration. No real account registration or reporting changes were used as tests.

Validation: 73 offline Python/UI regressions, isolated PostgreSQL fixture and tests/signup_affiliation_db.sql passed. Live ACL metadata verified. Full deployed browser and CI status must be checked separately.
