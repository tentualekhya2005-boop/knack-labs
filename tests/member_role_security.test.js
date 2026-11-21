import test from "node:test";
import assert from "node:assert/strict";
import { handleUpdateMemberRole } from "../src/routes/teams.js";
import { teams, memberships } from "../src/models/store.js";
import { ROLES, addMemberToTeam } from "../src/models/membership.js";
import { auditLogsStore } from "../src/models/audit_log.js";

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

function setupTeamFixture() {
  teams.length = 0;
  memberships.length = 0;
  auditLogsStore.length = 0;

  teams.push({ id: "team_1", name: "Engineering", owner_id: "usr_owner" });
  addMemberToTeam({ teamId: "team_1", userId: "usr_owner", role: ROLES.OWNER });
  addMemberToTeam({ teamId: "team_1", userId: "usr_admin", role: ROLES.ADMIN });
  addMemberToTeam({ teamId: "team_1", userId: "usr_member", role: ROLES.MEMBER });
  addMemberToTeam({ teamId: "team_1", userId: "usr_viewer", role: ROLES.VIEWER });
}

// 1. Viewer tries to update own role to admin: 403
test("1. Viewer tries to update own role to admin returns 403", () => {
  setupTeamFixture();
  const req = {
    headers: { "x-user-id": "usr_viewer" },
    params: { teamId: "team_1", userId: "usr_viewer" },
    body: { role: "admin" }
  };
  const res = createMockRes();
  handleUpdateMemberRole(req, res);
  assert.equal(res.statusCode, 403);
});

// 2. Viewer tries to update another member's role: 403
test("2. Viewer tries to update another member's role returns 403", () => {
  setupTeamFixture();
  const req = {
    headers: { "x-user-id": "usr_viewer" },
    params: { teamId: "team_1", userId: "usr_member" },
    body: { role: "admin" }
  };
  const res = createMockRes();
  handleUpdateMemberRole(req, res);
  assert.equal(res.statusCode, 403);
});

// 3. Member tries to update own role to admin: 403
test("3. Member tries to update own role to admin returns 403", () => {
  setupTeamFixture();
  const req = {
    headers: { "x-user-id": "usr_member" },
    params: { teamId: "team_1", userId: "usr_member" },
    body: { role: "admin" }
  };
  const res = createMockRes();
  handleUpdateMemberRole(req, res);
  assert.equal(res.statusCode, 403);
});

// 4. Member tries to update another member's role: 403
test("4. Member tries to update another member's role returns 403", () => {
  setupTeamFixture();
  const req = {
    headers: { "x-user-id": "usr_member" },
    params: { teamId: "team_1", userId: "usr_viewer" },
    body: { role: "admin" }
  };
  const res = createMockRes();
  handleUpdateMemberRole(req, res);
  assert.equal(res.statusCode, 403);
});

// 5. Admin updates a viewer to member: 200
test("5. Admin updates a viewer to member returns 200", () => {
  setupTeamFixture();
  const req = {
    headers: { "x-user-id": "usr_admin" },
    params: { teamId: "team_1", userId: "usr_viewer" },
    body: { role: "member" }
  };
  const res = createMockRes();
  handleUpdateMemberRole(req, res);
  assert.equal(res.statusCode, 200);
  assert.equal(res.body.member.role, "member");
  assert.equal(auditLogsStore.length, 1);
  assert.equal(auditLogsStore[0].action, "member.role_updated");
});

// 6. Admin updates a member to viewer: 200
test("6. Admin updates a member to viewer returns 200", () => {
  setupTeamFixture();
  const req = {
    headers: { "x-user-id": "usr_admin" },
    params: { teamId: "team_1", userId: "usr_member" },
    body: { role: "viewer" }
  };
  const res = createMockRes();
  handleUpdateMemberRole(req, res);
  assert.equal(res.statusCode, 200);
  assert.equal(res.body.member.role, "viewer");
});

// 7. Admin tries to promote member to owner: 403
test("7. Admin tries to promote member to owner returns 403", () => {
  setupTeamFixture();
  const req = {
    headers: { "x-user-id": "usr_admin" },
    params: { teamId: "team_1", userId: "usr_member" },
    body: { role: "owner" }
  };
  const res = createMockRes();
  handleUpdateMemberRole(req, res);
  assert.equal(res.statusCode, 403);
  assert.match(res.body.error.message, /only owners can promote/);
});

// 8. Admin tries to update own role: 403
test("8. Admin tries to update own role returns 403", () => {
  setupTeamFixture();
  const req = {
    headers: { "x-user-id": "usr_admin" },
    params: { teamId: "team_1", userId: "usr_admin" },
    body: { role: "viewer" }
  };
  const res = createMockRes();
  handleUpdateMemberRole(req, res);
  assert.equal(res.statusCode, 403);
  assert.equal(res.body.error.message, "Cannot modify your own role.");
});

// 9. Owner updates a member to admin: 200
test("9. Owner updates a member to admin returns 200", () => {
  setupTeamFixture();
  const req = {
    headers: { "x-user-id": "usr_owner" },
    params: { teamId: "team_1", userId: "usr_member" },
    body: { role: "admin" }
  };
  const res = createMockRes();
  handleUpdateMemberRole(req, res);
  assert.equal(res.statusCode, 200);
  assert.equal(res.body.member.role, "admin");
});

// 10. Owner promotes a member to owner: 200
test("10. Owner promotes a member to owner returns 200", () => {
  setupTeamFixture();
  const req = {
    headers: { "x-user-id": "usr_owner" },
    params: { teamId: "team_1", userId: "usr_member" },
    body: { role: "owner" }
  };
  const res = createMockRes();
  handleUpdateMemberRole(req, res);
  assert.equal(res.statusCode, 200);
  assert.equal(res.body.member.role, "owner");
});

// 11. Owner tries to update own role: 403
test("11. Owner tries to update own role returns 403", () => {
  setupTeamFixture();
  const req = {
    headers: { "x-user-id": "usr_owner" },
    params: { teamId: "team_1", userId: "usr_owner" },
    body: { role: "admin" }
  };
  const res = createMockRes();
  handleUpdateMemberRole(req, res);
  assert.equal(res.statusCode, 403);
  assert.equal(res.body.error.message, "Cannot modify your own role.");
});

// 12. Any user sends role value 'superadmin': 400
test("12. Any user sends role value superadmin returns 400", () => {
  setupTeamFixture();
  const req = {
    headers: { "x-user-id": "usr_owner" },
    params: { teamId: "team_1", userId: "usr_member" },
    body: { role: "superadmin" }
  };
  const res = createMockRes();
  handleUpdateMemberRole(req, res);
  assert.equal(res.statusCode, 400);
  assert.equal(res.body.error.code, "VALIDATION_ERROR");
});

// 13. Any user sends role value '': 400
test("13. Any user sends role value empty string returns 400", () => {
  setupTeamFixture();
  const req = {
    headers: { "x-user-id": "usr_owner" },
    params: { teamId: "team_1", userId: "usr_member" },
    body: { role: "" }
  };
  const res = createMockRes();
  handleUpdateMemberRole(req, res);
  assert.equal(res.statusCode, 400);
  assert.equal(res.body.error.code, "VALIDATION_ERROR");
});
