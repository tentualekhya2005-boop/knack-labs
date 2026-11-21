import test from "node:test";
import assert from "node:assert/strict";
import { handleCreateInvitation } from "../src/routes/invitations.js";
import { handleUpdateMemberRole } from "../src/routes/teams.js";
import { teams, memberships } from "../src/models/store.js";
import { addMemberToTeam, removeMemberFromTeam, ROLES } from "../src/models/membership.js";
import { createComment } from "../src/models/comment.js";
import { activityFeed, ACTIVITY_TYPES } from "../src/services/activity_feed.js";

function createMockRes() {
  return {
    statusCode: 200,
    headers: {},
    body: null,
    setHeader(key, val) {
      this.headers[key] = val;
    },
    end(payload) {
      this.body = payload ? JSON.parse(payload) : null;
    }
  };
}

function setupMatrixFixture() {
  teams.length = 0;
  memberships.length = 0;

  teams.push({ id: "team_mat_1", name: "Permission Matrix Team", owner_id: "usr_owner" });
  addMemberToTeam({ teamId: "team_mat_1", userId: "usr_owner", role: ROLES.OWNER });
  addMemberToTeam({ teamId: "team_mat_1", userId: "usr_admin", role: ROLES.ADMIN });
  addMemberToTeam({ teamId: "team_mat_1", userId: "usr_member", role: ROLES.MEMBER });
  addMemberToTeam({ teamId: "team_mat_1", userId: "usr_viewer", role: ROLES.VIEWER });
}

// 1. Admin Permissions
test("Permission Matrix: Admin can invite, remove members, change roles", () => {
  setupMatrixFixture();

  // Admin can invite
  const reqInvite = {
    headers: { "x-user-id": "usr_admin" },
    params: { teamId: "team_mat_1" },
    body: { email: "newcomer@example.com" }
  };
  const resInvite = createMockRes();
  handleCreateInvitation(reqInvite, resInvite);
  assert.equal(resInvite.statusCode, 201);

  // Admin can change roles
  const reqRole = {
    headers: { "x-user-id": "usr_admin" },
    params: { teamId: "team_mat_1", userId: "usr_viewer" },
    body: { role: "member" }
  };
  const resRole = createMockRes();
  handleUpdateMemberRole(reqRole, resRole);
  assert.equal(resRole.statusCode, 200);

  // Admin can remove members
  const removed = removeMemberFromTeam("team_mat_1", "usr_viewer");
  assert.equal(removed, true);
});

// 2. Member Permissions
test("Permission Matrix: Member can comment and view feed, but CANNOT invite or change roles", () => {
  setupMatrixFixture();

  // Member can comment
  const comment = createComment({
    taskId: "task_1",
    authorId: "usr_member",
    body: "Member progress update"
  });
  assert.ok(comment.id);

  // Member can view activity feed
  const events = activityFeed.getRecentEvents("team_mat_1");
  assert.ok(Array.isArray(events));

  // Member CANNOT invite (returns 403)
  const reqInvite = {
    headers: { "x-user-id": "usr_member" },
    params: { teamId: "team_mat_1" },
    body: { email: "unauthorized@example.com" }
  };
  const resInvite = createMockRes();
  handleCreateInvitation(reqInvite, resInvite);
  assert.equal(resInvite.statusCode, 403);
  assert.equal(resInvite.body.error.code, "FORBIDDEN");

  // Member CANNOT change roles (returns 403)
  const reqRole = {
    headers: { "x-user-id": "usr_member" },
    params: { teamId: "team_mat_1", userId: "usr_viewer" },
    body: { role: "admin" }
  };
  const resRole = createMockRes();
  handleUpdateMemberRole(reqRole, resRole);
  assert.equal(resRole.statusCode, 403);
  assert.equal(resRole.body.error.code, "FORBIDDEN");
});

// 3. Viewer Permissions
test("Permission Matrix: Viewer can view, but CANNOT invite or change roles", () => {
  setupMatrixFixture();

  // Viewer can view feed
  const events = activityFeed.getRecentEvents("team_mat_1");
  assert.ok(Array.isArray(events));

  // Viewer CANNOT invite (returns 403)
  const reqInvite = {
    headers: { "x-user-id": "usr_viewer" },
    params: { teamId: "team_mat_1" },
    body: { email: "unauthorized2@example.com" }
  };
  const resInvite = createMockRes();
  handleCreateInvitation(reqInvite, resInvite);
  assert.equal(resInvite.statusCode, 403);

  // Viewer CANNOT change roles (returns 403)
  const reqRole = {
    headers: { "x-user-id": "usr_viewer" },
    params: { teamId: "team_mat_1", userId: "usr_member" },
    body: { role: "admin" }
  };
  const resRole = createMockRes();
  handleUpdateMemberRole(reqRole, resRole);
  assert.equal(resRole.statusCode, 403);
});
