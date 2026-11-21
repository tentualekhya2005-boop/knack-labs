# Team Collaboration: Complete Task Tree & Prompt Specification

**Scenario:** Team Collaboration (TaskFlow API)  
**Skill:** AI-Augmented Engineering (Module 02)  
**Planning Approach:** Top-Down Decomposition (Option A)  
**Hard Ticket Limits:** Min 8 tasks, max 150 lines per task diff  

---

## 1. Dependency Graph & Critical Path

```
[Task 1: Team Model] ──────────────────────┐
       │                                   │
       ▼                                   ▼
[Task 2: Team CRUD Endpoints]     [Task 3: Membership Model]
       │                                   │
       │                                   ▼
       │                          [Task 4: RBAC Middleware]
       │                             /            \
       │                            /              \
       │                           ▼                ▼
       │                 [Task 5: Member Mgmt]   [Task 6: Invitation Model]
       │                           \                │
       │                            \               ▼
       │                             \   [Task 7: Invite Issue/Revoke]
       │                              \             │
       │                               \            ▼
       │                                ──► [Task 8: Invite Accept]
       ▼                                            │
[Task 9: Audit Logging Service] ◄────────────────────┘
       │
       ▼
[Task 10: Activity Feed Service]
```

**Critical Path:** `Task 1 → Task 3 → Task 4 → Task 6 → Task 7 → Task 8 → Task 9 → Task 10` (8 sequential steps).

---

## 2. Complete 10-Task Tree Specification

### Task 1: Team Model & Store
- **Task Name:** Create Team Data Model and Store Collection
- **Input Context Needed:** `package.json`, `src/models/store.js`
- **Expected Output:** New module `src/models/team.js` exporting `createTeamRecord`, `findTeamById`, and team schema validator.
- **Estimated Diff:** ~45 lines
- **Acceptance Criteria:** `createTeamRecord({ name: "Core", owner_id: "usr_1" })` returns a validated team entity with UUID and ISO timestamp; throws 400 on empty name.
- **Dependencies:** None (Root task).

### Task 2: Team Creation & Listing Routes
- **Task Name:** Implement Team CRUD API Endpoints
- **Input Context Needed:** `src/models/team.js`, `src/routes/index.js`
- **Expected Output:** `src/routes/teams.js` with `POST /teams` and `GET /teams`.
- **Estimated Diff:** ~70 lines
- **Acceptance Criteria:** `POST /teams` returns HTTP 201 with team payload; `GET /teams` returns array of teams matching caller id; invalid payload returns HTTP 400.
- **Dependencies:** Task 1.

### Task 3: Team Membership Model & Role Enums
- **Task Name:** Create Team Membership Entity and Role Definitions
- **Input Context Needed:** `src/models/team.js`, `src/models/store.js`
- **Expected Output:** `src/models/membership.js` with roles (`OWNER`, `ADMIN`, `MEMBER`, `GUEST`).
- **Estimated Diff:** ~50 lines
- **Acceptance Criteria:** `addMemberToTeam(teamId, userId, role)` validates role against enum; rejects duplicate user assignment with `409 Conflict`.
- **Dependencies:** Task 1.

### Task 4: RBAC Authorization Middleware
- **Task Name:** Implement Role-Based Access Control Middleware
- **Input Context Needed:** `src/models/membership.js`
- **Expected Output:** `src/middleware/rbac.js` exporting `requireTeamRole(minimumRole)`.
- **Estimated Diff:** ~65 lines
- **Acceptance Criteria:** Calling protected route with insufficient role returns `HTTP 403 Forbidden`; unauthenticated returns `HTTP 401 Unauthorized`; valid role passes next().
- **Dependencies:** Task 3.

### Task 5: Team Member Management Endpoints
- **Task Name:** Implement Member Roster & Removal Endpoints
- **Input Context Needed:** `src/models/membership.js`, `src/middleware/rbac.js`
- **Expected Output:** `src/routes/members.js` (`GET /teams/:id/members`, `DELETE /teams/:id/members/:userId`).
- **Estimated Diff:** ~70 lines
- **Acceptance Criteria:** Listing returns sanitized member list; deleting member by Admin succeeds; member cannot delete Team Owner (`HTTP 400`).
- **Dependencies:** Task 3, Task 4.

### Task 6: Invitation Model & Cryptographic Token Utility
- **Task Name:** Create Team Invitation Model and Token Utilities
- **Input Context Needed:** `src/models/store.js`, `src/models/membership.js`
- **Expected Output:** `src/models/invitation.js` exporting token generator and invitation lifecycle states.
- **Estimated Diff:** ~55 lines
- **Acceptance Criteria:** Creates invite record with SHA-256 hashed token, 7-day expiration timestamp, and `pending` status.
- **Dependencies:** Task 3.

### Task 7: Invitation Issuance & Revocation Endpoints
- **Task Name:** Implement Send and Revoke Invitation Routes
- **Input Context Needed:** `src/models/invitation.js`, `src/middleware/rbac.js`
- **Expected Output:** `src/routes/invitations.js` (`POST /teams/:id/invitations`, `DELETE /invitations/:id`).
- **Estimated Diff:** ~75 lines
- **Acceptance Criteria:** Admin can create invitation returning HTTP 201; non-admin receives HTTP 403; revoked invitation marks status `revoked`.
- **Dependencies:** Task 4, Task 6.

### Task 8: Invitation Acceptance Flow
- **Task Name:** Implement Public Invitation Acceptance Route
- **Input Context Needed:** `src/models/invitation.js`, `src/models/membership.js`
- **Expected Output:** Endpoint `POST /invitations/accept` in `src/routes/invitations.js`.
- **Estimated Diff:** ~65 lines
- **Acceptance Criteria:** Valid token adds user to team with designated role and marks invitation `accepted`; expired or used token returns `HTTP 400`.
- **Dependencies:** Task 5, Task 7.

### Task 9: Audit Logging Service for Sensitive Actions
- **Task Name:** Build Audit Trail Service for Administrative Operations
- **Input Context Needed:** `src/routes/teams.js`, `src/routes/members.js`, `src/routes/invitations.js`
- **Expected Output:** `src/services/audit.js` logging administrative events (`team.created`, `member.removed`, `invite.sent`).
- **Estimated Diff:** ~60 lines
- **Acceptance Criteria:** Audit records store actor, action, target_id, timestamp, and IP hash; immutable append-only storage.
- **Dependencies:** Task 2, Task 5, Task 7.

### Task 10: Real-Time Team Activity Feed Service
- **Task Name:** Build Chronological Team Activity Feed
- **Input Context Needed:** `src/services/audit.js`, `src/routes/teams.js`
- **Expected Output:** `src/services/activity.js` and `GET /teams/:id/activity`.
- **Estimated Diff:** ~75 lines
- **Acceptance Criteria:** Returns reverse-chronological list of team events with cursor-based pagination and tenant boundary filtering.
- **Dependencies:** Task 9.

---

## 3. Full Executable Prompts for First 3 Tasks

### Prompt 1 (Task 1: Team Model & Store)
```markdown
Create a Team data model module in `src/models/team.js` for the TaskFlow API project management service.

Context & Reference:
- Reference `package.json` for ES module syntax (`import`/`export`).
- Reference `src/models/store.js` which exports in-memory collections: `export const teams = [];`.

Requirements:
1. Export a function `validateTeamInput(data)`:
   - `name`: string, required, trimmed, min length 1, max length 100.
   - `description`: string, optional, max length 500.
   - Throws or returns an error object if invalid.
2. Export a function `createTeamRecord({ name, description, ownerId })`:
   - Validates input using `validateTeamInput`.
   - Generates a random unique ID prefixed with `team_` (e.g. using `crypto.randomUUID()`).
   - Assigns `created_at` and `updated_at` as ISO strings.
   - Appends the team to the `teams` array in `src/models/store.js` and returns the new team object.
3. Export a function `findTeamById(teamId)`:
   - Returns the matching team from `teams`, or `null` if not found.

Constraints:
- Use native Node.js libraries (`crypto`) only. Do NOT add new third-party dependencies to `package.json`.
- Do not modify files outside of `src/models/team.js` and `src/models/store.js`.
- Total diff must be under 60 lines.
```

### Prompt 2 (Task 2: Team Creation & Listing Routes)
```markdown
Create the team routing module in `src/routes/teams.js` and wire it into `src/routes/index.js`.

Context & Reference:
- Reference `src/models/team.js` for `createTeamRecord`, `findTeamById`, and validation.
- Reference `src/routes/index.js` for existing route registration patterns.

Requirements:
1. Implement route handlers:
   - `handleCreateTeam(req, res)`:
     - Extracts `{ name, description }` from `req.body` and `ownerId` from authenticated caller context `req.user.id`.
     - Returns HTTP 201 with the created team payload.
     - Returns HTTP 400 with `{ error: "Team name is required" }` if validation fails.
   - `handleListTeams(req, res)`:
     - Returns HTTP 200 with `{ teams: [...] }` containing teams owned by or accessible to `req.user.id`.
2. Update `src/routes/index.js`:
   - Export route metadata strings: `"POST /teams"` and `"GET /teams"`.
   - Wire the team route handlers into the route list function.

Constraints:
- Maintain consistent JSON error formats `{ error: string }`.
- Do NOT introduce third-party router frameworks; use pure Node request/response functions matching project style.
- Total diff must be under 80 lines.
```

### Prompt 3 (Task 3: Membership Model & Role Enums)
```markdown
Create the team membership module in `src/models/membership.js` managing user-team relationships and role assignments.

Context & Reference:
- Reference `src/models/store.js` for in-memory collections (export `memberships = []` if not present).
- Reference `src/models/team.js` for team ID structure.

Requirements:
1. Export frozen `ROLES` object:
   - `ROLES = { OWNER: "owner", ADMIN: "admin", MEMBER: "member", GUEST: "guest" }`.
2. Export `addMemberToTeam({ teamId, userId, role })`:
   - Validates that `role` exists in `ROLES` (defaults to `ROLES.MEMBER`).
   - Checks if `(teamId, userId)` already exists in `memberships`; if so, throws an error with code `DUPLICATE_MEMBER`.
   - Stores membership record with `id` (`mem_...`), `team_id`, `user_id`, `role`, and `joined_at`.
   - Returns the new membership record.
3. Export `getTeamMember(teamId, userId)`:
   - Returns the membership record or `null`.
4. Export `listMembersByTeam(teamId)`:
   - Returns array of membership records for the team.

Constraints:
- Strict role enumeration validation.
- Do NOT add external dependencies.
- Total diff must be under 70 lines.
```
