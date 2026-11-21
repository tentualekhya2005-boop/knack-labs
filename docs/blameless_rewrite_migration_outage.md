# Blameless Postmortem Rewrite: Database Outage (March 15th)

## Systemic Root Cause
The database deployment pipeline lacked automated schema migration validation against a production-scale staging database and permitted unreviewed migrations to execute directly against the production database cluster. Consequently, a schema migration containing a destructive `DROP INDEX` statement on the primary index of the `users` table was applied, causing all subsequent user authentication and lookup queries to degrade to sequential table scans, saturating PostgreSQL worker threads and exhausting the database connection pool.

---

## Systemic Contributing Factors

1. **Absence of Migration Linting and Automated Dry-Runs:** The continuous integration pipeline lacked automated database migration testing tools (such as migration linters or shadow database dry-runs) capable of detecting index removals, unindexed foreign keys, or table-locking schema alterations.
2. **Missing Repository Branch Protection and Approval Gates:** GitHub branch protection rules did not enforce mandatory multi-peer review or `CODEOWNERS` approval on paths modifying database schema files (`migrations/**`), allowing direct merges to production without second-party validation.
3. **Absence of Tooling-Enforced Deployment Freeze Windows:** The CI/CD release system lacked automated release gates restricting production deployments ahead of high-risk operational windows (such as Friday afternoons and weekends), leaving deployment timing solely to individual discretion.
4. **Lack of Automated Telemetry Alerting on Query Performance:** Database connection pool saturation and query execution time alerts were missing or thresholded too high, delaying incident awareness until end-users manually filed support tickets hours after the failure.

---

## Actionable Remediation Items

| # | Action | Owner | Deadline | Status |
|---|--------|-------|----------|--------|
| 1 | Add automated schema migration linter (`squawk` / `pg-eyeballs`) to CI pipeline to reject PRs containing unindexed queries or dropped indexes | Platform Team | 2024-03-29 | Open |
| 2 | Enforce GitHub branch protection requiring 2 mandatory reviews, including at least one `CODEOWNERS` approval from the Data Platform team on all `migrations/**` changes | Security & DevOps | 2024-03-22 | Open |
| 3 | Implement automated deployment freeze in CI/CD pipeline preventing production deployments between Friday 14:00 UTC and Monday 08:00 UTC | SRE Team | 2024-03-22 | Open |
| 4 | Deploy automated alerts triggering on database connection pool saturation (>80% for 1m) and P95 query latency spikes (>500ms for 2m) with PagerDuty escalation | SRE Team | 2024-03-29 | Open |
