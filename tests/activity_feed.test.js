import test from "node:test";
import assert from "node:assert/strict";
import { ActivityFeedService, ACTIVITY_TYPES } from "../src/services/activity_feed.js";

test("ActivityFeed: publishes event to subscribed client", () => {
  const feed = new ActivityFeedService();
  const received = [];

  const unsubscribe = feed.subscribe("team_alpha", (event) => {
    received.push(event);
  });

  const event = feed.publishEvent({
    teamId: "team_alpha",
    type: ACTIVITY_TYPES.MEMBER_JOINED,
    actorId: "usr_alice",
    payload: { role: "member" }
  });

  assert.equal(received.length, 1);
  assert.equal(received[0].id, event.id);
  assert.equal(received[0].type, "member.joined");
  assert.equal(received[0].actor_id, "usr_alice");

  unsubscribe();
});

test("ActivityFeed: enforces channel isolation between teams", () => {
  const feed = new ActivityFeedService();
  const alphaEvents = [];
  const betaEvents = [];

  feed.subscribe("team_alpha", (e) => alphaEvents.push(e));
  feed.subscribe("team_beta", (e) => betaEvents.push(e));

  feed.publishEvent({
    teamId: "team_alpha",
    type: ACTIVITY_TYPES.TEAM_CREATED,
    actorId: "usr_owner"
  });

  assert.equal(alphaEvents.length, 1);
  assert.equal(betaEvents.length, 0, "Team Beta must not receive Team Alpha events");
});

test("ActivityFeed: supports unsubscription and subscriber tracking", () => {
  const feed = new ActivityFeedService();
  const received = [];

  const listener = (e) => received.push(e);
  const unsub = feed.subscribe("team_gamma", listener);

  assert.equal(feed.getSubscriberCount("team_gamma"), 1);

  unsub();
  assert.equal(feed.getSubscriberCount("team_gamma"), 0);

  feed.publishEvent({
    teamId: "team_gamma",
    type: ACTIVITY_TYPES.MEMBER_INVITED,
    actorId: "usr_admin",
    payload: { email: "new@taskflow.dev" }
  });

  assert.equal(received.length, 0, "Listener must not receive events after unsubscribing");
});

test("ActivityFeed: replays buffered events since timestamp for reconnecting clients", () => {
  const feed = new ActivityFeedService();

  const pastTimestamp = new Date(Date.now() - 10000).toISOString();
  feed.publishEvent({
    teamId: "team_delta",
    type: ACTIVITY_TYPES.TEAM_CREATED,
    actorId: "usr_1"
  });

  const recentEvents = feed.getRecentEvents("team_delta", { sinceTimestamp: pastTimestamp });
  assert.equal(recentEvents.length, 1);
  assert.equal(recentEvents[0].type, ACTIVITY_TYPES.TEAM_CREATED);
});

test("ActivityFeed: rejects invalid event types with validation error", () => {
  const feed = new ActivityFeedService();

  assert.throws(
    () => {
      feed.publishEvent({
        teamId: "team_test",
        type: "unknown.wildcard.event"
      });
    },
    { code: "VALIDATION_ERROR" }
  );
});
