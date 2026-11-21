# TaskFlow System-Level Context & Per-Task Bundles

**Scenario:** Team Collaboration  
**Skill:** AI-Augmented Engineering (Module 03)  
**Strategy:** Layered Context (Option B)  
**Date:** 2026-11-21  

---

## Part 1: System-Level Context Document (Reusable Across All Prompts)

### 1. Architecture Summary
- **Runtime & Framework:** Node.js (v20+ ES Modules), Native Node HTTP request handlers, and native `node:test` runner.
- **Folder Organization:**
  - `src/models/`: Domain entity definitions, validators, and in-memory stores (`store.js`).
  - `src/routes/`: Route controllers and endpoint registries (`index.js`).
  - `src/middleware/`: Pipeline interceptors for authentication and RBAC guards.
  - `src/services/`: Business workflows, audit logging, and activity event feeds.
  - `tests/`: Automated unit and integration tests.
- **Database & Storage:** In-memory array collections (`users`, `teams`, `invitations`, `memberships`) exported from `src/models/store.js`.

### 2. Standardized Coding Conventions
- **Variable & Function Naming:** `camelCase` for variables, properties, and functions (`createTeamRecord`, `findTeamById`).
- **File Naming:** `snake_case` or `kebab-case` for file basenames with clear semantic domain prefixes (`src/models/team.js`, `src/routes/teams.js`).
- **Error Handling Convention:**
  All error responses MUST use `sendErrorResponse(res, statusCode, code, message)` imported from `src/utils/errors.js`.
  Do NOT format error responses manually or inline.
  Example usage: `sendErrorResponse(res, 400, "VALIDATION_ERROR", "Team name is required")`
  Standard schema produced:
  ```json
  {
    "error": {
      "code": "VALIDATION_ERROR",
      "message": "Team name is required and cannot be empty"
    }
  }
  ```
  Standard Status Codes:
  - `400`: `VALIDATION_ERROR` or `BAD_REQUEST` (malformed data or contract breach)
  - `401`: `UNAUTHORIZED` (missing or invalid credentials)
  - `403`: `FORBIDDEN` (insufficient role permissions)
  - `404`: `RESOURCE_NOT_FOUND` (entity does not exist)
  - `409`: `CONFLICT` or `DUPLICATE_MEMBER` (duplicate entry or uniqueness violation)
  - `500`: `INTERNAL_ERROR` (unexpected system failure)

### 3. Non-Negotiable System Constraints
- **Zero Third-Party Dependency Drift:** Use only native Node.js standard libraries (`crypto`, `assert`). Do NOT add npm dependencies without architectural signoff.
- **Strict Reuse of Existing Middleware:** Always reuse existing header auth patterns (`x-user-id` or Bearer token extraction) rather than writing custom auth logic.
- **Atomic Diffs:** Every task output must produce under 150 lines of diff.

---

## Part 2: Per-Task Context Bundles

### Task Bundle 1: Team Model & Store
- **Task Goal:** Implement team entity creation and schema validation.
- **Files to Read:** `package.json`, `src/models/store.js` (shows in-memory array pattern).
- **Files to Modify/Create:** `src/models/team.js`, `src/models/store.js`.
- **Expected Deliverable:** Exported functions `createTeamRecord`, `findTeamById`, `validateTeamInput`.

### Task Bundle 2: Team CRUD Endpoints
- **Task Goal:** Expose team creation (`POST /teams`) and listing (`GET /teams`).
- **Files to Read:** `src/models/team.js` (entity structure), `src/routes/index.js` (route registration pattern), `src/utils/errors.js` (standardized error responder).
- **Files to Modify/Create:** `src/routes/teams.js`, `src/routes/index.js`.
- **Expected Deliverable:** Request handlers enforcing structured `{ error: { code, message } }` formatting via `sendErrorResponse` and returning 201/200/400/401 statuses.

### Task Bundle 3: Team Membership Model & Role Enums
- **Task Goal:** Create many-to-many user-team membership tracking with RBAC roles.
- **Files to Read:** `src/models/store.js`, `src/models/team.js` (team ID prefix `team_`).
- **Files to Modify/Create:** `src/models/membership.js`, `src/models/store.js`.
- **Expected Deliverable:** Exported frozen `ROLES` enum (`OWNER`, `ADMIN`, `MEMBER`, `GUEST`), `addMemberToTeam`, `getTeamMember`, and `listMembersByTeam`.
