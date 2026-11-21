import test from "node:test";
import assert from "node:assert/strict";
import { createTeamRecord } from "../src/models/team.js";
import { teams, memberships, invitations } from "../src/models/store.js";
import { createInvitationRecord } from "../src/models/invitation.js";
import { addMemberToTeam, ROLES } from "../src/models/membership.js";
import { createComment, commentsStore } from "../src/models/comment.js";
import { parseMentions, extractUniqueUsernames } from "../src/utils/mention_parser.js";
import { recordAuditEvent, queryAuditLogsByTeam, auditLogsStore } from "../src/models/audit_log.js";
import { activityFeed, ACTIVITY_TYPES } from "../src/services/activity_feed.js";

test("Capstone E2E: Full 6-step end-to-end team collaboration lifecycle", () => {
  // Clean state for isolation
  teams.length = 0;
  memberships.length = 0;
  invitations.length = 0;
  commentsStore.length = 0;
  auditLogsStore.length = 0;
  activityFeed.clear();

  const userA = "usr_alice";
  const userB = "usr_bob";

  // Step 1: User A creates a team
  const team = createTeamRecord({
    name: "Nebula Core",
    description: "Core infrastructure engineering",
    ownerId: userA
  });
  assert.ok(team.id);
  assert.equal(team.name, "Nebula Core");
  assert.equal(team.owner_id, userA);

  recordAuditEvent({
    teamId: team.id,
    action: "team.created",
    actorId: userA,
    details: { teamName: team.name }
  });

  // Step 2: User A invites User B to the team as a member
  const invite = createInvitationRecord({
    teamId: team.id,
    email: "bob@example.com",
    invitedBy: userA
  });
  assert.ok(invite.id);
  assert.equal(invite.team_id, team.id);
  assert.equal(invite.email, "bob@example.com");

  recordAuditEvent({
    teamId: team.id,
    action: "invitation.sent",
    actorId: userA,
    details: { invitationId: invite.id, email: invite.email, role: "member" }
  });

  // Step 3: User B accepts the invitation
  invite.status = "accepted";
  const memberB = addMemberToTeam({
    teamId: team.id,
    userId: userB,
    role: ROLES.MEMBER
  });
  assert.equal(memberB.user_id, userB);
  assert.equal(memberB.role, ROLES.MEMBER);

  recordAuditEvent({
    teamId: team.id,
    action: "invitation.accepted",
    actorId: userB,
    details: { invitationId: invite.id }
  });

  // Step 4: User B comments on a task in the team, with an @mention of User A
  const taskId = "task_deploy_prod";
  const commentBody = "Ready for deployment! CC @alice for signoff.";
  const comment = createComment({
    taskId,
    authorId: userB,
    body: commentBody
  });
  assert.ok(comment.id);
  assert.equal(comment.authorId, userB);

  const mentions = parseMentions(comment.body);
  const mentionedUsernames = extractUniqueUsernames(comment.body);
  assert.deepEqual(mentionedUsernames, ["alice"]);

  recordAuditEvent({
    teamId: team.id,
    action: "comment.created",
    actorId: userB,
    details: { commentId: comment.id, taskId, mentions: mentionedUsernames }
  });

  // Step 5: User A checks the activity feed and sees User B's comment
  activityFeed.publishEvent({
    teamId: team.id,
    type: ACTIVITY_TYPES.MEMBER_JOINED,
    actorId: userB,
    payload: { commentId: comment.id, body: comment.body, mentions: mentionedUsernames }
  });

  const recentEvents = activityFeed.getRecentEvents(team.id, { limit: 10 });
  assert.ok(recentEvents.length >= 1);
  const matchingEvent = recentEvents.find((e) => e.actor_id === userB);
  assert.ok(matchingEvent);
  assert.equal(matchingEvent.payload.commentId, comment.id);

  // Step 6: Admin checks the audit log and sees entries for all 4 key lifecycle actions
  const auditEntries = queryAuditLogsByTeam(team.id, { limit: 50 });
  const actionList = auditEntries.map((e) => e.action);

  assert.ok(actionList.includes("team.created"), "Audit log must contain team.created");
  assert.ok(actionList.includes("invitation.sent"), "Audit log must contain invitation.sent");
  assert.ok(actionList.includes("invitation.accepted"), "Audit log must contain invitation.accepted");
  assert.ok(actionList.includes("comment.created"), "Audit log must contain comment.created");
  assert.equal(auditEntries.length, 4);
});
