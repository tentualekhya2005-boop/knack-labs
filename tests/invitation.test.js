import test from "node:test";
import assert from "node:assert/strict";
import { handleCreateTeam } from "../src/routes/teams.js";
import { handleCreateInvitation } from "../src/routes/invitations.js";
import { teams, users, memberships, invitations } from "../src/models/store.js";
import { createTeamRecord } from "../src/models/team.js";
import { addMemberToTeam, ROLES } from "../src/models/membership.js";

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

test("Test 1: Invite a user who is already a team member returns 409 Conflict", () => {
  teams.length = 0;
  users.length = 0;
  memberships.length = 0;
  invitations.length = 0;

  const team = createTeamRecord({ name: "Core Engineering", ownerId: "usr_alice" });
  users.push({ id: "usr_bob", email: "bob@taskflow.dev" });
  addMemberToTeam({ teamId: team.id, userId: "usr_bob", role: ROLES.MEMBER });

  const req = {
    headers: { "x-user-id": "usr_alice" },
    params: { teamId: team.id },
    body: { email: "bob@taskflow.dev" }
  };
  const res = createMockRes();

  handleCreateInvitation(req, res);

  assert.equal(res.statusCode, 409);
  assert.equal(res.body.error.code, "CONFLICT");
  assert.match(res.body.error.message, /already a member/);
});

test("Test 2: Create a team with an empty name returns 400 Bad Request", () => {
  const req = {
    headers: { "x-user-id": "usr_alice" },
    body: { name: "   " }
  };
  const res = createMockRes();

  handleCreateTeam(req, res);

  assert.equal(res.statusCode, 400);
  assert.equal(res.body.error.code, "VALIDATION_ERROR");
  assert.match(res.body.error.message, /name is required/);
});

test("Test 3: Call the invitation endpoint without authentication returns 401 Unauthorized", () => {
  const req = {
    headers: {},
    params: { teamId: "team_123" },
    body: { email: "charlie@taskflow.dev" }
  };
  const res = createMockRes();

  handleCreateInvitation(req, res);

  assert.equal(res.statusCode, 401);
  assert.equal(res.body.error.code, "UNAUTHORIZED");
});

test("Test 4: Call the invitation endpoint as a non-member/non-admin returns 403 Forbidden", () => {
  teams.length = 0;
  memberships.length = 0;

  const team = createTeamRecord({ name: "Private Ops", ownerId: "usr_alice" });

  const req = {
    headers: { "x-user-id": "usr_stranger" },
    params: { teamId: team.id },
    body: { email: "david@taskflow.dev" }
  };
  const res = createMockRes();

  handleCreateInvitation(req, res);

  assert.equal(res.statusCode, 403);
  assert.equal(res.body.error.code, "FORBIDDEN");
  assert.match(res.body.error.message, /only team owners or admins/);
});

test("Test 5: Send an invitation with an invalid email format returns 400 Bad Request", () => {
  teams.length = 0;
  const team = createTeamRecord({ name: "Security Team", ownerId: "usr_alice" });

  const req = {
    headers: { "x-user-id": "usr_alice" },
    params: { teamId: team.id },
    body: { email: "not-an-email" }
  };
  const res = createMockRes();

  handleCreateInvitation(req, res);

  assert.equal(res.statusCode, 400);
  assert.equal(res.body.error.code, "VALIDATION_ERROR");
  assert.match(res.body.error.message, /valid email address/);
});

test("IDOR Fix: Admin user can send invitation and returns 201 Created", () => {
  teams.length = 0;
  memberships.length = 0;
  invitations.length = 0;

  const team = createTeamRecord({ name: "Alpha Squad", ownerId: "usr_alice" });
  addMemberToTeam({ teamId: team.id, userId: "usr_bob_admin", role: ROLES.ADMIN });

  const req = {
    headers: { "x-user-id": "usr_bob_admin" },
    params: { teamId: team.id },
    body: { email: "newhire@taskflow.dev" }
  };
  const res = createMockRes();

  handleCreateInvitation(req, res);

  assert.equal(res.statusCode, 201);
  assert.ok(res.body.invitation);
  assert.equal(res.body.invitation.email, "newhire@taskflow.dev");
  assert.equal(res.body.invitation.team_id, team.id);
  assert.equal(res.body.invitation.status, "pending");
});

test("IDOR Fix: Non-admin team member cannot send invitation and returns 403 Forbidden", () => {
  teams.length = 0;
  memberships.length = 0;
  invitations.length = 0;

  const team = createTeamRecord({ name: "Alpha Squad", ownerId: "usr_alice" });
  addMemberToTeam({ teamId: team.id, userId: "usr_charlie_member", role: ROLES.MEMBER });

  const req = {
    headers: { "x-user-id": "usr_charlie_member" },
    params: { teamId: team.id },
    body: { email: "outsider@taskflow.dev" }
  };
  const res = createMockRes();

  handleCreateInvitation(req, res);

  assert.equal(res.statusCode, 403);
  assert.equal(res.body.error.code, "FORBIDDEN");
  assert.match(res.body.error.message, /only team owners or admins/);
});
