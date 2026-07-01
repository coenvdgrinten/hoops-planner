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

export interface AuthUser {
  id: number;
  username: string;
  email: string;
  is_staff: boolean;
}

export interface AuthResponse {
  token: string;
  user: AuthUser;
}

const TOKEN_KEY = "auth_token";
const USER_KEY = "auth_user";

export function getToken(): string | null {
  return localStorage.getItem(TOKEN_KEY);
}

export function getUser(): AuthUser | null {
  const raw = localStorage.getItem(USER_KEY);
  if (!raw) return null;
  try {
    return JSON.parse(raw);
  } catch {
    return null;
  }
}

export function setAuth(token: string, user: AuthUser) {
  localStorage.setItem(TOKEN_KEY, token);
  localStorage.setItem(USER_KEY, JSON.stringify(user));
}

export function clearAuth() {
  localStorage.removeItem(TOKEN_KEY);
  localStorage.removeItem(USER_KEY);
}

async function request<T>(url: string, options?: RequestInit): Promise<T> {
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
  };
  const token = getToken();
  if (token) {
    headers["Authorization"] = `Token ${token}`;
  }
  const res = await fetch(`${API}${url}`, {
    headers,
    ...options,
  });
  if (!res.ok) {
    // If 401, clear auth and rethrow
    if (res.status === 401) {
      clearAuth();
      window.dispatchEvent(new CustomEvent("auth:logout"));
    }
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

export function importSchedule(seasonName: string, csvText: string, replace?: boolean) {
  return request<{ games_created: number; games_updated: number; tasks: number }>("/seasons/import_schedule/", {
    method: "POST",
    body: JSON.stringify({ season_name: seasonName, csv_text: csvText, replace: replace ?? false }),
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

export function updatePlayerCoachedTeams(playerId: number, teamIds: number[]) {
  return request<Player>(`/players/${playerId}/`, {
    method: "PATCH",
    body: JSON.stringify({ coached_teams: teamIds }),
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

export function createGame(data: {
  season: number;
  home_team_id: number;
  away_team: string;
  date: string;
  time: string;
  court: string;
  half: string;
}) {
  return request<Game>("/games/", {
    method: "POST",
    body: JSON.stringify(data),
  });
}

export function updateGame(gameId: number, data: Partial<Game>) {
  return request<Game>(`/games/${gameId}/`, {
    method: "PATCH",
    body: JSON.stringify(data),
  });
}

export function deleteGame(gameId: number) {
  return request<void>(`/games/${gameId}/`, { method: "DELETE" });
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
export function getPlayerStats(playerId: number, seasonName?: string, half?: string) {
  const params = new URLSearchParams();
  if (seasonName) params.set("season", seasonName);
  if (half) params.set("half", half);
  const qs = params.toString() ? `?${params.toString()}` : "";
  return request<Record<string, unknown>>(`/players/${playerId}/stats/${qs}`);
}

export function getPlayerUpcoming(playerId: number) {
  return request<UpcomingAssignment[]>(`/players/${playerId}/upcoming/`);
}

export function getSeasonStats(seasonId: number, half?: string) {
  const qs = half ? `?half=${half}` : "";
  return request<SeasonStats>(`/seasons/${seasonId}/stats/${qs}`);
}

export function getLeaderboard(seasonId: number, half?: string) {
  const qs = half ? `?half=${half}` : "";
  return request<LeaderboardEntry[]>(`/seasons/${seasonId}/leaderboard/${qs}`);
}

// Auth
export function login(username: string, password: string) {
  return request<AuthResponse>("/auth/login/", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ username, password }),
  });
}

export function register(username: string, password: string, email: string) {
  return request<AuthResponse>("/auth/register/", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ username, password, email }),
  });
}

export function me() {
  return request<AuthUser>("/auth/me/");
}
