# Architectural Decision Records (ADR) - TaskFlow API

## ADR-01: Zero-Dependency Architecture & Native Standard Library
- **Context**: External npm dependencies introduce supply-chain vulnerability surface (e.g. SolarWinds / event-stream vectors).
- **Decision**: Rely exclusively on Node.js built-in modules (`node:crypto` for UUIDs, `node:events` for pub/sub, `node:test` and `node:assert/strict` for testing).
- **Consequences**: Zero third-party vulnerability exposure, deterministic startup times (<350ms test runs), zero dependency rot.

---

## ADR-02: Strict Layered Role-Based Access Control (RBAC)
- **Context**: Module 07 identified that simple membership checks (`isTeamMember`) permit vertical privilege escalation when regular members or viewers invoke administrative endpoints.
- **Decision**:
  - Distinguish explicitly between **Authentication** (caller identity), **Tenant Scoping** (membership in team), and **Authorization** (administrative capability).
  - Enforce least privilege: only team `owner` and `admin` can invite members or alter roles.
  - Invariants: A user cannot modify their own role (`callerId !== userId`); admins cannot promote anyone to `owner`; all role inputs must validate against the frozen `ROLES` enum.
- **Consequences**: Complete immunity to BFLA privilege escalation, validated by 13 negative test cases.

---

## ADR-03: Bounded In-Memory Event Replay & Isolated Channels
- **Context**: Real-time team collaboration requires instant activity distribution while protecting client socket connections from cross-tenant crosstalk and memory leaks.
- **Decision**:
  - Implement `ActivityFeedService` with per-team channel namespacing (`team:${teamId}`).
  - Maintain a bounded circular FIFO buffer (default limit 50 events) per team to enable reconnecting clients to catch up without unbounded RAM growth.
  - Provide explicit unsubscription callbacks returned from `.subscribe()` to eliminate EventEmitter memory leaks.
- **Consequences**: Reliable real-time event delivery with deterministic memory consumption.

---

## ADR-04: Immutable Audit Trail with Domain Event Decoupling
- **Context**: Statutory compliance and forensic accountability require an auditable trail of all security and state mutations without coupling API routes to storage engines.
- **Decision**:
  - Use an event-to-audit glue layer (`src/services/comment_audit_glue.js`) that captures domain mutations asynchronously and writes structured records (`id`, `teamId`, `action`, `actorId`, `details`, `timestamp`).
  - Sanitize payload objects to prevent accidental credential or PII logging.
- **Consequences**: Complete lifecycle observability with loose coupling across services.
