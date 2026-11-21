import test from "node:test";
import assert from "node:assert/strict";
import { createTeamRecord, findTeamById, validateTeamInput } from "../src/models/team.js";
import { teams } from "../src/models/store.js";

test("Task 1: creates team record with valid inputs and UUID", () => {
  teams.length = 0; // reset
  const team = createTeamRecord({ name: "Core Infrastructure", description: "Infra team", ownerId: "usr_admin1" });
  assert.ok(team.id.startsWith("team_"));
  assert.equal(team.name, "Core Infrastructure");
  assert.equal(team.description, "Infra team");
  assert.equal(team.owner_id, "usr_admin1");
  assert.ok(team.created_at);
  assert.equal(team.created_at, team.updated_at);
  assert.equal(teams.length, 1);
});

test("Task 1: findTeamById finds persisted team", () => {
  teams.length = 0;
  const created = createTeamRecord({ name: "DevOps", ownerId: "usr_admin2" });
  const found = findTeamById(created.id);
  assert.ok(found);
  assert.equal(found.id, created.id);
  assert.equal(found.name, "DevOps");
  assert.equal(findTeamById("team_nonexistent"), null);
});

test("Task 1: rejects empty team name with validation error", () => {
  assert.throws(() => {
    createTeamRecord({ name: "   ", ownerId: "usr_admin1" });
  }, /Invalid team data: name is required/);
});

test("Task 1: rejects missing ownerId with validation error", () => {
  assert.throws(() => {
    createTeamRecord({ name: "Security", ownerId: "" });
  }, /Invalid team data: ownerId is required/);
});
