import { createTeamRecord, findTeamById } from "../models/team.js";
import { teams, memberships } from "../models/store.js";
import { updateMemberRole, getTeamMember, ROLES } from "../models/membership.js";
import { recordAuditEvent } from "../models/audit_log.js";
import { sendErrorResponse } from "../utils/errors.js";

export function handleCreateTeam(req, res) {
  if (!req.body || typeof req.body !== "object") {
    sendErrorResponse(res, 400, "BAD_REQUEST", "Invalid payload: body is required");
    return;
  }

  const userId = req.user?.id || req.headers?.["x-user-id"];
  if (!userId) {
    sendErrorResponse(res, 401, "UNAUTHORIZED", "Unauthorized: user identity required");
    return;
  }

  try {
    const team = createTeamRecord({
      name: req.body.name,
      description: req.body.description,
      ownerId: userId
    });

    res.statusCode = 201;
    res.setHeader("Content-Type", "application/json");
    res.end(JSON.stringify({ team }));
  } catch (err) {
    sendErrorResponse(res, 400, "VALIDATION_ERROR", err.message);
  }
}

export function handleListTeams(req, res) {
  const userId = req.user?.id || req.headers?.["x-user-id"];
  if (!userId) {
    sendErrorResponse(res, 401, "UNAUTHORIZED", "Unauthorized: user identity required");
    return;
  }

  const userTeams = teams.filter((t) => t.owner_id === userId);
  res.statusCode = 200;
  res.setHeader("Content-Type", "application/json");
  res.end(JSON.stringify({ teams: userTeams }));
}

export function handleUpdateMemberRole(req, res) {
  const callerId = req.user?.id || req.headers?.["x-user-id"];
  if (!callerId) {
    sendErrorResponse(res, 401, "UNAUTHORIZED", "Unauthorized: user identity required");
    return;
  }

  const teamId = req.params?.teamId;
  const targetUserId = req.params?.userId;
  if (!teamId || !targetUserId) {
    sendErrorResponse(res, 400, "BAD_REQUEST", "teamId and userId are required");
    return;
  }

  // Constraint 2: Cannot modify own role
  if (callerId === targetUserId) {
    sendErrorResponse(res, 403, "FORBIDDEN", "Cannot modify your own role.");
    return;
  }

  const team = teams.find((t) => t.id === teamId);
  if (!team) {
    sendErrorResponse(res, 404, "NOT_FOUND", "Team not found");
    return;
  }

  // Caller role determination
  const isOwner = team.owner_id === callerId;
  const callerMembership = memberships.find((m) => m.team_id === teamId && m.user_id === callerId);
  const callerRole = isOwner ? "owner" : callerMembership?.role;

  // Constraint 1: Only admin or owner can modify member roles
  if (callerRole !== "owner" && callerRole !== "admin") {
    sendErrorResponse(res, 403, "FORBIDDEN", "Insufficient permissions to modify team member roles");
    return;
  }

  // Constraint 3: Validate role enum (admin, member, viewer, owner)
  const role = req.body?.role;
  const allowedRoles = ["admin", "member", "viewer", "owner"];
  if (!role || typeof role !== "string" || !allowedRoles.includes(role)) {
    sendErrorResponse(res, 400, "VALIDATION_ERROR", `Invalid role: must be one of ${allowedRoles.join(", ")}`);
    return;
  }

  // Constraint 4: Admin cannot promote to owner
  if (callerRole === "admin" && role === "owner") {
    sendErrorResponse(res, 403, "FORBIDDEN", "Forbidden: only owners can promote a member to owner");
    return;
  }

  const targetMember = getTeamMember(teamId, targetUserId);
  if (!targetMember) {
    sendErrorResponse(res, 404, "NOT_FOUND", `Member ${targetUserId} not found in team ${teamId}`);
    return;
  }

  const oldRole = targetMember.role;

  try {
    const updated = updateMemberRole({ teamId, userId: targetUserId, role });

    // Constraint 5: Audit log entry for role change
    recordAuditEvent({
      teamId,
      action: "member.role_updated",
      actorId: callerId,
      details: {
        targetUserId,
        oldRole,
        newRole: role,
        requestedBy: callerId
      }
    });

    res.statusCode = 200;
    res.setHeader("Content-Type", "application/json");
    res.end(JSON.stringify({ member: updated }));
  } catch (err) {
    if (err.code === "NOT_FOUND") {
      sendErrorResponse(res, 404, "NOT_FOUND", err.message);
    } else {
      sendErrorResponse(res, 400, "VALIDATION_ERROR", err.message);
    }
  }
}
