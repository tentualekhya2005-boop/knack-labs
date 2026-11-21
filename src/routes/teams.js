import { createTeamRecord, findTeamById } from "../models/team.js";
import { teams } from "../models/store.js";
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
