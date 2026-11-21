# Parallel Agent Interface Contracts

**Module:** 06 (Parallel Agent Management)  
**Strategy:** Interface-First (Option A)  
**Date:** 2026-11-21  

---

## Agent 1 Contract: Comment Threads
- **Creates:** `src/models/comment.js`, `tests/comments.test.js`
- **Reads (Immutable):** `src/models/store.js`
- **Modifies:** None (isolated domain entity)
- **Data Shape:**
  ```javascript
  {
    id: "cmt_<UUID>",
    taskId: string,
    authorId: string,
    body: string, // 1 - 5000 chars
    parentId: string | null,
    createdAt: ISOString,
    updatedAt: ISOString
  }
  ```
- **Public API:** `createComment(data)`, `listCommentsByTask(taskId)`, `findCommentById(id)`

---

## Agent 2 Contract: @Mention Parsing Utility
- **Creates:** `src/utils/mention_parser.js`, `tests/mention.test.js`
- **Reads (Immutable):** None (pure stateless utility)
- **Modifies:** None
- **Data Shape:**
  ```javascript
  {
    raw: "@username",
    username: "username",
    position: { start: number, end: number }
  }
  ```
- **Public API:** `parseMentions(text)`, `extractUniqueUsernames(text)`

---

## Agent 3 Contract: Team Action Audit Logging
- **Creates:** `src/models/audit_log.js`, `tests/audit_log.test.js`
- **Reads (Immutable):** `src/models/store.js`
- **Modifies:** None
- **Data Shape:**
  ```javascript
  {
    id: "aud_<UUID>",
    teamId: string,
    action: string,
    actorId: string,
    details: object,
    timestamp: ISOString
  }
  ```
- **Public API:** `recordAuditEvent(data)`, `queryAuditLogsByTeam(teamId, options)`
