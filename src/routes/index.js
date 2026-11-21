import { handleCreateTeam, handleListTeams, handleUpdateMemberRole } from "./teams.js";

export function listRoutes() {
  return ["GET /health", "GET /teams", "POST /teams"];
}

export { handleCreateTeam, handleListTeams, handleUpdateMemberRole };
