import test from "node:test";
import assert from "node:assert/strict";
import { handleCreateTeam, handleListTeams } from "../src/routes/teams.js";
import { teams } from "../src/models/store.js";

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

test("Task 2: handleCreateTeam creates team and returns 201", () => {
  teams.length = 0;
  const req = {
    headers: { "x-user-id": "usr_test1" },
    body: { name: "Platform Team", description: "Infra & CI" }
  };
  const res = createMockRes();

  handleCreateTeam(req, res);

  assert.equal(res.statusCode, 201);
  assert.ok(res.body.team);
  assert.equal(res.body.team.name, "Platform Team");
  assert.equal(res.body.team.owner_id, "usr_test1");
});

test("Task 2: handleCreateTeam rejects missing name with structured 400 error", () => {
  const req = {
    headers: { "x-user-id": "usr_test1" },
    body: { name: "   " }
  };
  const res = createMockRes();

  handleCreateTeam(req, res);

  assert.equal(res.statusCode, 400);
  assert.ok(res.body.error);
  assert.equal(typeof res.body.error, "object");
  assert.equal(res.body.error.code, "VALIDATION_ERROR");
  assert.match(res.body.error.message, /name is required/);
});

test("Task 2: handleListTeams returns user teams with 200", () => {
  teams.length = 0;
  const req = { headers: { "x-user-id": "usr_test1" } };
  const res = createMockRes();

  // Create two teams, one for test1, one for test2
  handleCreateTeam({ headers: { "x-user-id": "usr_test1" }, body: { name: "Team Alpha" } }, createMockRes());
  handleCreateTeam({ headers: { "x-user-id": "usr_test2" }, body: { name: "Team Beta" } }, createMockRes());

  handleListTeams(req, res);

  assert.equal(res.statusCode, 200);
  assert.equal(res.body.teams.length, 1);
  assert.equal(res.body.teams[0].name, "Team Alpha");
});

test("Task 2: rejects unauthenticated requests with structured 401 error", () => {
  const req = { headers: {}, body: { name: "Orphan Team" } };
  const res = createMockRes();

  handleCreateTeam(req, res);
  assert.equal(res.statusCode, 401);
  assert.ok(res.body.error);
  assert.equal(typeof res.body.error, "object");
  assert.equal(res.body.error.code, "UNAUTHORIZED");
});
