import test from "node:test";
import assert from "node:assert/strict";
import { recordAuditEvent, queryAuditLogsByTeam, auditLogsStore } from "../src/models/audit_log.js";

test("AuditLog: records structured audit event with UUID", () => {
  auditLogsStore.length = 0;
  const event = recordAuditEvent({
    teamId: "team_infra",
    action: "member.invited",
    actorId: "usr_alice",
    details: { inviteeEmail: "dev@taskflow.dev", role: "member" }
  });

  assert.ok(event.id.startsWith("aud_"));
  assert.equal(event.teamId, "team_infra");
  assert.equal(event.action, "member.invited");
  assert.equal(event.actorId, "usr_alice");
  assert.equal(event.details.inviteeEmail, "dev@taskflow.dev");
  assert.ok(event.timestamp);
});

test("AuditLog: rejects missing action with VALIDATION_ERROR", () => {
  assert.throws(
    () => {
      recordAuditEvent({
        teamId: "team_infra",
        action: "",
        actorId: "usr_alice"
      });
    },
    { code: "VALIDATION_ERROR" }
  );
});

test("AuditLog: queries logs scoped to target team", () => {
  auditLogsStore.length = 0;
  recordAuditEvent({ teamId: "team_1", action: "team.created", actorId: "usr_1" });
  recordAuditEvent({ teamId: "team_2", action: "team.created", actorId: "usr_2" });

  const team1Logs = queryAuditLogsByTeam("team_1");
  assert.equal(team1Logs.length, 1);
  assert.equal(team1Logs[0].teamId, "team_1");
});
