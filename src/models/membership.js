import { randomUUID } from "node:crypto";
import { memberships } from "./store.js";

export const ROLES = Object.freeze({
  OWNER: "owner",
  ADMIN: "admin",
  MEMBER: "member",
  GUEST: "guest"
});

export function addMemberToTeam({ teamId, userId, role = ROLES.MEMBER }) {
  if (!teamId || typeof teamId !== "string") {
    throw new Error("Invalid membership: teamId is required");
  }
  if (!userId || typeof userId !== "string") {
    throw new Error("Invalid membership: userId is required");
  }

  const validRoles = Object.values(ROLES);
  if (!validRoles.includes(role)) {
    throw new Error(`Invalid membership role: must be one of ${validRoles.join(", ")}`);
  }

  const existing = getTeamMember(teamId, userId);
  if (existing) {
    const err = new Error(`User ${userId} is already a member of team ${teamId}`);
    err.code = "DUPLICATE_MEMBER";
    throw err;
  }

  const record = {
    id: `mem_${randomUUID()}`,
    team_id: teamId,
    user_id: userId,
    role,
    joined_at: new Date().toISOString()
  };

  memberships.push(record);
  return record;
}

export function getTeamMember(teamId, userId) {
  if (!teamId || !userId) return null;
  return memberships.find((m) => m.team_id === teamId && m.user_id === userId) || null;
}

export function listMembersByTeam(teamId) {
  if (!teamId) return [];
  return memberships.filter((m) => m.team_id === teamId);
}

export function removeMemberFromTeam(teamId, userId) {
  const index = memberships.findIndex((m) => m.team_id === teamId && m.user_id === userId);
  if (index === -1) {
    return false;
  }
  memberships.splice(index, 1);
  return true;
}
