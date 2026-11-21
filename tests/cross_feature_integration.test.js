import test from "node:test";
import assert from "node:assert/strict";
import { createComment, commentsStore } from "../src/models/comment.js";
import { parseMentions, extractUniqueUsernames } from "../src/utils/mention_parser.js";
import { recordAuditEvent, queryAuditLogsByTeam, auditLogsStore } from "../src/models/audit_log.js";
import { activityFeed, ACTIVITY_TYPES } from "../src/services/activity_feed.js";

test("Cross-Feature: comment creation extracts mentions, logs audit event, and broadcasts activity", () => {
  commentsStore.length = 0;
  auditLogsStore.length = 0;

  const teamId = "team_cross_100";
  const authorId = "usr_alice";
  const commentText = "Hey @bob and @charlie, please review the security checklist!";

  // 1. Create comment
  const comment = createComment({
    taskId: "tsk_security_audit",
    authorId,
    body: commentText
  });
  assert.ok(comment.id);

  // 2. Extract mentions
  const mentions = parseMentions(comment.body);
  const mentionedUsernames = extractUniqueUsernames(comment.body);
  assert.equal(mentions.length, 2);
  assert.deepEqual(mentionedUsernames.sort(), ["bob", "charlie"]);

  // 3. Record audit event
  const auditEntry = recordAuditEvent({
    teamId,
    action: "comment.created",
    actorId: authorId,
    details: {
      commentId: comment.id,
      taskId: comment.taskId,
      mentions: mentionedUsernames
    }
  });
  assert.equal(auditEntry.action, "comment.created");
  assert.equal(auditEntry.details.commentId, comment.id);

  // 4. Activity feed broadcast
  const receivedEvents = [];
  const unsub = activityFeed.subscribe(teamId, (e) => receivedEvents.push(e));

  activityFeed.publishEvent({
    teamId,
    type: ACTIVITY_TYPES.MEMBER_INVITED,
    actorId: authorId,
    payload: { commentId: comment.id, mentions: mentionedUsernames }
  });

  assert.equal(receivedEvents.length, 1);
  assert.equal(receivedEvents[0].actor_id, "usr_alice");

  unsub();
});
