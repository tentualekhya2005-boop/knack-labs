import test from "node:test";
import assert from "node:assert/strict";
import { addMemberToTeam, getTeamMember, listMembersByTeam, removeMemberFromTeam, ROLES } from "../src/models/membership.js";
import { memberships } from "../src/models/store.js";

test("Task 3: addMemberToTeam creates membership with default role", () => {
  memberships.length = 0;
  const mem = addMemberToTeam({ teamId: "team_1", userId: "usr_1" });
  assert.ok(mem.id.startsWith("mem_"));
  assert.equal(mem.team_id, "team_1");
  assert.equal(mem.user_id, "usr_1");
  assert.equal(mem.role, ROLES.MEMBER);
  assert.ok(mem.joined_at);
  assert.equal(memberships.length, 1);
});

test("Task 3: rejects invalid role with descriptive error", () => {
  assert.throws(() => {
    addMemberToTeam({ teamId: "team_1", userId: "usr_2", role: "superadmin" });
  }, /Invalid membership role: must be one of/);
});

test("Task 3: rejects duplicate membership with DUPLICATE_MEMBER code", () => {
  memberships.length = 0;
  addMemberToTeam({ teamId: "team_1", userId: "usr_1", role: ROLES.ADMIN });
  assert.throws(() => {
    addMemberToTeam({ teamId: "team_1", userId: "usr_1", role: ROLES.MEMBER });
  }, (err) => err.code === "DUPLICATE_MEMBER");
});

test("Task 3: getTeamMember and listMembersByTeam return matching memberships", () => {
  memberships.length = 0;
  addMemberToTeam({ teamId: "team_alpha", userId: "usr_1", role: ROLES.OWNER });
  addMemberToTeam({ teamId: "team_alpha", userId: "usr_2", role: ROLES.MEMBER });
  addMemberToTeam({ teamId: "team_beta", userId: "usr_3", role: ROLES.ADMIN });

  assert.equal(listMembersByTeam("team_alpha").length, 2);
  assert.equal(listMembersByTeam("team_beta").length, 1);
  assert.equal(getTeamMember("team_alpha", "usr_1").role, ROLES.OWNER);
  assert.equal(getTeamMember("team_alpha", "usr_nonexistent"), null);
});

test("Task 3: removeMemberFromTeam removes member successfully", () => {
  memberships.length = 0;
  addMemberToTeam({ teamId: "team_1", userId: "usr_1" });
  assert.equal(removeMemberFromTeam("team_1", "usr_1"), true);
  assert.equal(memberships.length, 0);
  assert.equal(removeMemberFromTeam("team_1", "usr_1"), false);
});
