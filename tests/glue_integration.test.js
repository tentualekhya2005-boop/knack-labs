import test from "node:test";
import assert from "node:assert/strict";
import { EventEmitter } from "node:events";
import { wireCommentAuditEvents } from "../src/services/comment_audit_glue.js";
import { queryAuditLogsByTeam, auditLogsStore } from "../src/models/audit_log.js";

test("Glue Integration: maps comment.created/updated/deleted events to structured audit entries", () => {
  auditLogsStore.length = 0;
  const bus = new EventEmitter();

  const unwire = wireCommentAuditEvents(bus);

  const teamId = "team_alpha_101";

  // 1. Emit comment.created
  bus.emit("comment.created", {
    teamId,
    commentId: "cmt_1",
    taskId: "tsk_1",
    authorId: "usr_alice",
    timestamp: new Date().toISOString()
  });

  // 2. Emit comment.updated
  bus.emit("comment.updated", {
    teamId,
    commentId: "cmt_1",
    taskId: "tsk_1",
    authorId: "usr_alice",
    timestamp: new Date().toISOString()
  });

  // 3. Emit comment.deleted
  bus.emit("comment.deleted", {
    teamId,
    commentId: "cmt_1",
    taskId: "tsk_1",
    authorId: "usr_alice",
    timestamp: new Date().toISOString()
  });

  const logs = queryAuditLogsByTeam(teamId);
  assert.equal(logs.length, 3);
  assert.equal(logs[0].action, "comment.created");
  assert.equal(logs[0].details.resourceType, "comment");
  assert.equal(logs[0].details.resourceId, "cmt_1");

  assert.equal(logs[1].action, "comment.updated");
  assert.equal(logs[1].details.resourceType, "comment");

  assert.equal(logs[2].action, "comment.deleted");
  assert.equal(logs[2].details.resourceType, "comment");

  unwire();
});
