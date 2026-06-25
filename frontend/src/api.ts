import type {
  CandidateDetail,
  EligiblePlayer,
  Game,
  LeaderboardEntry,
  Player,
  Season,
  SeasonStats,
  Task,
  TaskAssignment,
  TaskWithAssignments,
  Team,
  TeamEligibility,
  UpcomingAssignment,
} from "./types";

const API = "/api";

async function request<T>(url: string, options?: RequestInit): Promise<T> {
  const res = await fetch(`${API}${url}`, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  if (!res.ok) {
    const text = await res.text();
    let message = text;
    try {
      const json = JSON.parse(text);
      if (Array.isArray(json) && json.length > 0) {
        message = json[0];
      } else if (typeof json === "object" && json.detail) {
        message = json.detail;
      }
    } catch {
      // Not JSON, keep raw text
    }
    throw new Error(message);
  }
  // 204 No Content has no body to parse
  if (res.status === 204) return undefined as T;
  const json = await res.json();
  return json as T;
}

// Seasons
export function getSeasons() {
  return request<Season[]>("/seasons/");
}

export function importSchedule(seasonName: string, csvText: string) {
  return request<{ games: number; tasks: number }>("/seasons/import_schedule/", {
    method: "POST",
    body: JSON.stringify({ season_name: seasonName, csv_text: csvText }),
  });
}

// Teams
export function getTeams() {
  return request<Team[]>("/teams/");
}

// Players
export function getPlayers() {
  return request<Player[]>("/players/");
}

export function updatePlayerCert(playerId: number, cert: string) {
  return request<Player>(`/players/${playerId}/`, {
    method: "PATCH",
    body: JSON.stringify({ referee_certification: cert }),
  });
}

export function importMembers(csvText: string) {
  return request<{ players: number; teams: number }>("/players/import_members/", {
    method: "POST",
    body: JSON.stringify({ csv_text: csvText, upsert: true }),
  });
}

// Games
export function getGames(season: number) {
  return request<Game[]>(`/games/?season=${season}`);
}

// Tasks
export function getTasks(game: number) {
  return request<Task[]>(`/tasks/?game=${game}`);
}

export function getTasksWithAssignments(game: number) {
  return request<TaskWithAssignments[]>(`/games/${game}/tasks_with_assignments/`);
}

export function getEligiblePlayers(task: number) {
  return request<EligiblePlayer[]>(`/players/eligible/?task=${task}`);
}

export function getSuggestions(task: number) {
  return request<Player[]>(`/tasks/${task}/suggestions/`);
}

export function getCandidateDetails(task: number) {
  return request<CandidateDetail[]>(`/tasks/${task}/candidate_details/`);
}

export function getTeamEligibility(task: number) {
  return request<TeamEligibility[]>(`/tasks/${task}/team_eligibility/`);
}

// Task Assignments
export function getAssignments(task: number) {
  return request<TaskAssignment[]>(`/assignments/?task=${task}`);
}

export function createAssignment(task: number, playerId: number) {
  return request<TaskAssignment>(`/assignments/`, {
    method: "POST",
    body: JSON.stringify({ task_id: task, player_id: playerId }),
  });
}

export function deleteAssignment(id: number) {
  return request<void>(`/assignments/${id}/`, { method: "DELETE" });
}

// Statistics
export function getPlayerStats(playerId: number, seasonName?: string) {
  const qs = seasonName ? `?season=${seasonName}` : "";
  return request<Record<string, unknown>>(`/players/${playerId}/stats/${qs}`);
}

export function getPlayerUpcoming(playerId: number) {
  return request<UpcomingAssignment[]>(`/players/${playerId}/upcoming/`);
}

export function getSeasonStats(seasonId: number) {
  return request<SeasonStats>(`/seasons/${seasonId}/stats/`);
}

export function getLeaderboard(seasonId: number) {
  return request<LeaderboardEntry[]>(`/seasons/${seasonId}/leaderboard/`);
}
