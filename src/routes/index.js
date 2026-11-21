import { handleCreateTeam, handleListTeams } from "./teams.js";

export function listRoutes() {
  return ["GET /health", "GET /teams", "POST /teams"];
}

export { handleCreateTeam, handleListTeams };
