import { EventEmitter } from "node:events";
import { randomUUID } from "node:crypto";

export const ACTIVITY_TYPES = Object.freeze({
  TEAM_CREATED: "team.created",
  MEMBER_INVITED: "member.invited",
  MEMBER_JOINED: "member.joined",
  MEMBER_REMOVED: "member.removed"
});

export class ActivityFeedService {
  constructor(options = {}) {
    this.emitter = new EventEmitter();
    this.emitter.setMaxListeners(options.maxListeners || 100);
    this.eventBuffer = new Map(); // teamId -> array of events
    this.bufferLimit = options.bufferLimit || 50;
    this.subscribers = new Map(); // teamId -> Set of client callbacks
  }

  publishEvent({ teamId, type, actorId, payload = {} }) {
    if (!teamId || typeof teamId !== "string" || !teamId.trim()) {
      const err = new Error("Invalid activity event: teamId is required");
      err.code = "VALIDATION_ERROR";
      throw err;
    }
    const validTypes = Object.values(ACTIVITY_TYPES);
    if (!type || !validTypes.includes(type)) {
      const err = new Error(`Invalid activity type: must be one of ${validTypes.join(", ")}`);
      err.code = "VALIDATION_ERROR";
      throw err;
    }

    const event = {
      id: `act_${randomUUID()}`,
      team_id: teamId.trim(),
      type,
      actor_id: actorId || "system",
      payload,
      timestamp: new Date().toISOString()
    };

    // Store in bounded buffer
    if (!this.eventBuffer.has(teamId)) {
      this.eventBuffer.set(teamId, []);
    }
    const buffer = this.eventBuffer.get(teamId);
    buffer.push(event);
    if (buffer.length > this.bufferLimit) {
      buffer.shift();
    }

    // Scoped channel broadcast
    this.emitter.emit(`team:${teamId}`, event);
    return event;
  }

  subscribe(teamId, callback) {
    if (!teamId || typeof teamId !== "string") {
      throw new Error("Invalid subscription: teamId string is required");
    }
    if (typeof callback !== "function") {
      throw new Error("Invalid subscription: callback function is required");
    }

    if (!this.subscribers.has(teamId)) {
      this.subscribers.set(teamId, new Set());
    }
    this.subscribers.get(teamId).add(callback);

    const eventKey = `team:${teamId}`;
    this.emitter.on(eventKey, callback);

    // Return unsubscribe function for client teardown
    return () => this.unsubscribe(teamId, callback);
  }

  unsubscribe(teamId, callback) {
    if (!teamId || typeof callback !== "function") return false;

    const eventKey = `team:${teamId}`;
    this.emitter.removeListener(eventKey, callback);

    const teamSubs = this.subscribers.get(teamId);
    if (teamSubs) {
      teamSubs.delete(callback);
      if (teamSubs.size === 0) {
        this.subscribers.delete(teamId);
      }
    }
    return true;
  }

  getRecentEvents(teamId, { sinceTimestamp = null, limit = 20 } = {}) {
    if (!teamId) return [];
    const buffer = this.eventBuffer.get(teamId) || [];
    let filtered = buffer;
    if (sinceTimestamp) {
      const sinceDate = new Date(sinceTimestamp).getTime();
      filtered = buffer.filter((e) => new Date(e.timestamp).getTime() >= sinceDate);
    }
    return filtered.slice(-limit);
  }

  getSubscriberCount(teamId) {
    return this.subscribers.get(teamId)?.size || 0;
  }

  clear() {
    this.emitter.removeAllListeners();
    this.eventBuffer.clear();
    this.subscribers.clear();
  }
}

export const activityFeed = new ActivityFeedService();
