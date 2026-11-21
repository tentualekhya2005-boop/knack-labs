# TaskFlow API Architecture & Extension Summary

**Scenario:** Team Collaboration  
**Skill:** AI-Augmented Engineering (Module 01)  
**Date:** 2026-11-21  

---

## 1. Workspace & Directory Structure

```
.
├── package.json              # ES module manifest with Node.js native test runner
├── src/                      # Core application source directory
│   ├── models/               # Domain entities and in-memory datastores
│   │   └── store.js          # Exported collections (users, teams, invitations)
│   ├── routes/               # API route definitions and endpoint registries
│   │   └── index.js          # Route enumeration (GET /health, GET /teams)
│   └── services/             # Application business logic and domain services
│       └── workspace.js      # Workspace metadata and service descriptors
├── tests/                    # Automated test suite
│   └── starter.test.js       # Native Node.js test asserting route visibility
└── progress/                 # Milestone progress, evidence logs, and audit files
    └── ai-augmented-engineering/module-01/
```

---

## 2. Key Data Models

Located in `src/models/store.js`:
- **`users`**: Represents team members and system accounts.
  - Fields: `id`, `email`, `name`, `role`, `created_at`.
- **`teams`**: Represents organizational team workspaces.
  - Fields: `id`, `name`, `owner_id`, `created_at`.
- **`invitations`**: Manages team onboarding and invitations.
  - Fields: `id`, `team_id`, `email`, `role`, `token`, `status` (`pending`, `accepted`, `revoked`), `expires_at`.

---

## 3. API Routes & Endpoints

Located in `src/routes/index.js`:
- `GET /health` -- Operational health check returning HTTP 200 and system readiness status.
- `GET /teams` -- Lists all accessible teams for the authenticated user context.

---

## 4. Authentication & Authorization Mechanism

- **Authentication:** Token-based authentication using HTTP `Authorization: Bearer <token>` headers.
- **Authorization & RBAC:** Role-based permissions mapped to teams:
  - `owner`: Full administrative rights (team deletion, billing, role modifications).
  - `admin`: Member invitations, channel/thread moderation, settings.
  - `member`: Standard collaboration (comments, task creation, mentions).
  - `guest`: Read-only access to explicitly shared threads.

---

## 5. Storage Architecture

- **Active Layer:** In-memory store collections in `src/models/store.js` supporting fast unit and contract tests with zero external infrastructure dependencies.
- **Production Extension Path:** Configurable connection adapter backed by PostgreSQL with transactional schemas, foreign keys, and migration tracking.

---

## 6. Codebase Extension Points

1. **New API Routes:**
   - *Location:* `src/routes/` using domain-specific files (e.g., `src/routes/invitations.js`, `src/routes/members.js`).
   - *Registration Pattern:* Import route handlers into `src/routes/index.js` and register with central dispatcher.
2. **New Data Models:**
   - *Location:* `src/models/`, defining schema validation, index declarations, and relationship definitions.
3. **Middleware Pipeline:**
   - *Location:* `src/middleware/` (e.g., `auth.js`, `logger.js`, `rate-limiter.js`). Middleware executes sequentially on incoming requests before passing control to route handlers.
4. **Background / Asynchronous Jobs:**
   - *Location:* `src/services/` or `src/jobs/` for async event publishing (e.g. sending invitation emails, populating real-time activity feeds).
