import { randomUUID } from "node:crypto";
import { teams } from "./store.js";

export function validateTeamInput(data) {
  if (!data || typeof data !== "object") {
    throw new Error("Invalid team data: payload must be an object");
  }

  const name = typeof data.name === "string" ? data.name.trim() : "";
  if (!name || name.length < 1 || name.length > 100) {
    throw new Error("Invalid team data: name is required and must be between 1 and 100 characters");
  }

  const description = typeof data.description === "string" ? data.description.trim() : "";
  if (description && description.length > 500) {
    throw new Error("Invalid team data: description cannot exceed 500 characters");
  }

  if (!data.ownerId || typeof data.ownerId !== "string" || !data.ownerId.trim()) {
    throw new Error("Invalid team data: ownerId is required");
  }

  return {
    name,
    description: description || null,
    ownerId: data.ownerId.trim()
  };
}

export function createTeamRecord(data) {
  const validated = validateTeamInput(data);
  const now = new Date().toISOString();

  const team = {
    id: `team_${randomUUID()}`,
    name: validated.name,
    description: validated.description,
    owner_id: validated.ownerId,
    created_at: now,
    updated_at: now
  };

  teams.push(team);
  return team;
}

export function findTeamById(teamId) {
  if (!teamId || typeof teamId !== "string") {
    return null;
  }
  return teams.find((t) => t.id === teamId) || null;
}
