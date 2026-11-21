import { randomUUID } from "node:crypto";

export const auditLogsStore = [];

export function recordAuditEvent({ teamId, action, actorId, details = {} }) {
  if (!teamId || typeof teamId !== "string" || !teamId.trim()) {
    const err = new Error("Invalid audit event: teamId is required");
    err.code = "VALIDATION_ERROR";
    throw err;
  }
  if (!action || typeof action !== "string" || !action.trim()) {
    const err = new Error("Invalid audit event: action is required");
    err.code = "VALIDATION_ERROR";
    throw err;
  }
  if (!actorId || typeof actorId !== "string" || !actorId.trim()) {
    const err = new Error("Invalid audit event: actorId is required");
    err.code = "VALIDATION_ERROR";
    throw err;
  }

  const record = {
    id: `aud_${randomUUID()}`,
    teamId: teamId.trim(),
    action: action.trim(),
    actorId: actorId.trim(),
    details: details && typeof details === "object" ? details : {},
    timestamp: new Date().toISOString()
  };

  auditLogsStore.push(record);
  return record;
}

export function queryAuditLogsByTeam(teamId, { limit = 50 } = {}) {
  if (!teamId) return [];
  return auditLogsStore
    .filter((log) => log.teamId === teamId)
    .slice(-limit);
}
