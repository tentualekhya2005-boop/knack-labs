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
- **`users`**: Represents team members and system accounts (`id`, `email`, `name`, `role`, `created_at`).
- **`teams`**: Represents organizational team workspaces (`id`, `name`, `owner_id`, `created_at`).
- **`invitations`**: Manages team onboarding and invitations (`id`, `team_id`, `email`, `role`, `token`, `status`, `expires_at`).

---

## 3. API Routes & Endpoints

Located in `src/routes/index.js`:
- `GET /health` -- Operational health check returning HTTP 200 and system readiness status.
- `GET /teams` -- Lists all accessible teams for the authenticated user context.

---

## 4. Codebase Extension Points

1. **New API Routes:** `src/routes/` with modular file-per-domain registration in `src/routes/index.js`.
2. **New Data Models:** `src/models/` defining schemas and exported stores.
3. **Middleware Pipeline:** `src/middleware/` for authentication checkpoints and logging.
4. **Background / Asynchronous Jobs:** `src/services/` or `src/jobs/` for async event dispatch.
