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
  All error responses adhere to the standard JSON error schema:
  ```json
  {
    "error": {
      "code": "VALIDATION_ERROR",
      "message": "Team name is required and cannot be empty"
    }
  }
  ```

### 3. Non-Negotiable System Constraints
- Zero external npm dependencies.
- Strict reuse of existing auth mechanisms.
- Diffs bounded under 150 lines per task.
