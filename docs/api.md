# TaskFlow API - Technical Specification & Integration Reference

## 1. Authentication & Security Headers

All authenticated endpoints require the client identity header:
```http
x-user-id: <user_id_string>
```
If omitted or empty, endpoints return:
```json
{
  "error": {
    "code": "UNAUTHORIZED",
    "message": "Unauthorized: user identity required"
  }
}
```

---

## 2. API Endpoints

### 2.1 Create Team
- **Method**: `POST`
- **Path**: `/teams`
- **Headers**: `x-user-id: <userId>`
- **Request Body**:
  ```json
  {
    "name": "Platform Team",
    "description": "Optional team description (0-500 chars)"
  }
  ```
- **Validation Rules**: `name` must be a non-empty string between 1 and 100 characters.
- **Success Response (201 Created)**:
  ```json
  {
    "team": {
      "id": "team_abc123",
      "name": "Platform Team",
      "description": "Optional team description",
      "owner_id": "usr_alice",
      "created_at": "2026-11-21T18:00:00.000Z"
    }
  }
  ```
- **Error Responses**: `400 BAD_REQUEST` / `VALIDATION_ERROR`, `401 UNAUTHORIZED`.

---

### 2.2 List User Teams
- **Method**: `GET`
- **Path**: `/teams`
- **Headers**: `x-user-id: <userId>`
- **Success Response (200 OK)**:
  ```json
  {
    "teams": [
      {
        "id": "team_abc123",
        "name": "Platform Team",
        "owner_id": "usr_alice"
      }
    ]
  }
  ```

---

### 2.3 Send Team Invitation
- **Method**: `POST`
- **Path**: `/teams/:teamId/invitations`
- **Headers**: `x-user-id: <adminOrOwnerId>`
- **Authorization**: Caller must be team owner or member with `admin` or `owner` role.
- **Request Body**:
  ```json
  {
    "email": "developer@company.com"
  }
  ```
- **Success Response (201 Created)**:
  ```json
  {
    "invitation": {
      "id": "inv_xyz789",
      "team_id": "team_abc123",
      "email": "developer@company.com",
      "invited_by": "usr_alice",
      "status": "pending",
      "created_at": "2026-11-21T18:00:00.000Z"
    }
  }
  ```
- **Error Responses**:
  - `401 UNAUTHORIZED`: Missing identity.
  - `403 FORBIDDEN`: Caller is not team owner or admin.
  - `404 NOT_FOUND`: Team does not exist.
  - `409 CONFLICT`: Target email is already a team member or has a pending invitation.

---

### 2.4 Update Team Member Role
- **Method**: `PUT`
- **Path**: `/teams/:teamId/members/:userId`
- **Headers**: `x-user-id: <adminOrOwnerId>`
- **Authorization Constraints**:
  - Requester must be team owner or admin (`isTeamAdminOrOwner`).
  - Users cannot modify their own role (`callerId !== userId`).
  - Admins cannot promote members to `owner` (only owners can assign `owner`).
  - `role` must be in `['admin', 'member', 'viewer', 'owner']`.
- **Request Body**:
  ```json
  {
    "role": "admin"
  }
  ```
- **Success Response (200 OK)**:
  ```json
  {
    "member": {
      "id": "mem_111",
      "team_id": "team_abc123",
      "user_id": "usr_bob",
      "role": "admin",
      "updated_at": "2026-11-21T18:05:00.000Z"
    }
  }
  ```
- **Error Responses**:
  - `400 VALIDATION_ERROR`: Invalid or empty role.
  - `403 FORBIDDEN`: Insufficient privileges, self-modification attempt, or admin promoting to owner.
  - `404 NOT_FOUND`: Team or member not found.

---

### 2.5 Create Task Comment
- **Method**: `POST`
- **Function**: `createComment({ taskId, authorId, body, parentId })`
- **Validation**: `body` between 1 and 5000 chars; `taskId` and `authorId` required.
- **Mentions**: Auto-parsed from `@username` syntax.
- **Side Effects**: Emits `member.role_updated` / `comment.created` to audit log.

---

### 2.6 Real-Time Activity Feed
- **Service**: `activityFeed` (`ActivityFeedService`)
- **Operations**:
  - `publishEvent({ teamId, type, actorId, payload })`
  - `subscribe(teamId, callback)` -> returns unsubscribe closure
  - `getRecentEvents(teamId, { sinceTimestamp, limit })`
