import { teams, memberships } from "../models/store.js";
import { createInvitationRecord, listInvitationsByTeam } from "../models/invitation.js";
import { sendErrorResponse } from "../utils/errors.js";

export function handleCreateInvitation(req, res) {
  const userId = req.user?.id || req.headers?.["x-user-id"];
  if (!userId) {
    sendErrorResponse(res, 401, "UNAUTHORIZED", "Unauthorized: user identity required");
    return;
  }

  const teamId = req.params?.teamId;
  if (!teamId) {
    sendErrorResponse(res, 400, "BAD_REQUEST", "Team ID is required in URL path");
    return;
  }

  const team = teams.find((t) => t.id === teamId);
  if (!team) {
    sendErrorResponse(res, 404, "NOT_FOUND", "Team not found");
    return;
  }

  // Authorization: must be team owner or admin
  const isOwner = team.owner_id === userId;
  const isAdmin = memberships.some(
    (m) => m.team_id === teamId && m.user_id === userId && (m.role === "admin" || m.role === "owner")
  );

  if (!isOwner && !isAdmin) {
    sendErrorResponse(res, 403, "FORBIDDEN", "Forbidden: only team owners or admins can send invitations");
    return;
  }

  const email = req.body?.email;
  if (!email || typeof email !== "string") {
    sendErrorResponse(res, 400, "VALIDATION_ERROR", "Validation failed: valid email address is required");
    return;
  }

  try {
    const invitation = createInvitationRecord({
      teamId,
      email,
      invitedBy: userId
    });

    res.statusCode = 201;
    res.setHeader("Content-Type", "application/json");
    res.end(JSON.stringify({ invitation }));
  } catch (err) {
    if (err.code === "ALREADY_MEMBER" || err.code === "DUPLICATE_INVITATION") {
      sendErrorResponse(res, 409, "CONFLICT", err.message);
    } else if (err.code === "VALIDATION_ERROR") {
      sendErrorResponse(res, 400, "VALIDATION_ERROR", err.message);
    } else if (err.code === "NOT_FOUND") {
      sendErrorResponse(res, 404, "NOT_FOUND", err.message);
    } else {
      sendErrorResponse(res, 500, "INTERNAL_ERROR", "An unexpected error occurred");
    }
  }
}
