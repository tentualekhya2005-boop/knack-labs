import { randomUUID } from "node:crypto";
import { invitations, teams, memberships, users } from "./store.js";

const EMAIL_REGEX = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

export function validateInvitationInput({ teamId, email, invitedBy }) {
  if (!teamId || typeof teamId !== "string" || !teamId.trim()) {
    const err = new Error("Invalid invitation: teamId is required");
    err.code = "VALIDATION_ERROR";
    throw err;
  }

  if (!email || typeof email !== "string" || !EMAIL_REGEX.test(email.trim())) {
    const err = new Error("Invalid invitation: email must be a valid email address");
    err.code = "VALIDATION_ERROR";
    throw err;
  }

  if (!invitedBy || typeof invitedBy !== "string" || !invitedBy.trim()) {
    const err = new Error("Invalid invitation: invitedBy userId is required");
    err.code = "VALIDATION_ERROR";
    throw err;
  }

  return {
    teamId: teamId.trim(),
    email: email.trim().toLowerCase(),
    invitedBy: invitedBy.trim()
  };
}

export function createInvitationRecord(data) {
  const validated = validateInvitationInput(data);

  // Check if team exists
  const team = teams.find((t) => t.id === validated.teamId);
  if (!team) {
    const err = new Error(`Team ${validated.teamId} not found`);
    err.code = "NOT_FOUND";
    throw err;
  }

  // Check if email belongs to an existing user who is already a member
  const existingUser = users.find((u) => u.email === validated.email);
  if (existingUser) {
    const isMember = memberships.some(
      (m) => m.team_id === validated.teamId && m.user_id === existingUser.id
    );
    if (isMember) {
      const err = new Error(`User with email ${validated.email} is already a member of this team`);
      err.code = "ALREADY_MEMBER";
      throw err;
    }
  }

  // Check for duplicate pending invitation
  const duplicate = invitations.find(
    (inv) => inv.team_id === validated.teamId && inv.email === validated.email && inv.status === "pending"
  );
  if (duplicate) {
    const err = new Error(`Pending invitation already exists for ${validated.email}`);
    err.code = "DUPLICATE_INVITATION";
    throw err;
  }

  const record = {
    id: `inv_${randomUUID()}`,
    team_id: validated.teamId,
    email: validated.email,
    invited_by: validated.invitedBy,
    status: "pending",
    created_at: new Date().toISOString()
  };

  invitations.push(record);
  return record;
}

export function listInvitationsByTeam(teamId) {
  if (!teamId) return [];
  return invitations.filter((inv) => inv.team_id === teamId);
}
