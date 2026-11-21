# Production Rollback & Emergency Recovery Plan

## 1. Rollback Trigger Criteria
A production rollback or deployment freeze is triggered immediately if:
- **Severity 1 (SEV1)**: Any authorization bypass, cross-tenant data leakage, or unauthenticated state mutation occurs.
- **Severity 2 (SEV2)**: API error rate exceeds 1% of total requests over a rolling 5-minute window or crash loop occurs.

## 2. Immediate Rollback Runbook (Estimated Time to Recovery: < 3 minutes)
1. **Traffic Diversion**:
   - Re-route incoming traffic to the previous stable release artifact (`v1.0.0-stable`) via load balancer or container orchestrator traffic split (100% previous version).
2. **Database Schema State**:
   - The TaskFlow API schema additions (memberships, comments, audit_logs) are non-destructive and backward-compatible (additive only).
   - No table drops or column alterations required during rollback.
3. **Cache & Socket Invalidation**:
   - Flush active in-memory activity feeds and socket sessions:
     ```bash
     npm run restart
     ```
4. **Verification**:
   - Execute health check probe:
     ```bash
     curl -f http://localhost:3000/health || exit 1
     ```
   - Execute automated sanity suite:
     ```bash
     npm test
     ```

## 3. Communication & Incident Ownership
- **Incident Commander**: Alekhya Tentu (Tech Lead)
- **Stakeholder Notification**: Post immediate status advisory in `#incident-management` within 5 minutes of trigger.
- **Postmortem**: Hold blameless engineering postmortem within 24 hours of incident mitigation.
