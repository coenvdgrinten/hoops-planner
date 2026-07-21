import type {
  AvailabilityDay,
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
  // DRF pagination wraps list responses in {count, next, previous, results}.
  // Unwrap to the bare array so callers can keep treating lists as arrays.
  // Follow `next` links so the UI always receives the complete dataset even
  // when a list spans multiple pages.
  if (
    json &&
    typeof json === "object" &&
    !Array.isArray(json) &&
    Array.isArray((json as { results?: unknown }).results)
  ) {
    return (await collectPages(json as Paginated<T>, headers)) as T;
  }
  return json as T;
}

interface Paginated<T> {
  count: number;
  next: string | null;
  previous: string | null;
  results: T[];
}

/**
 * Walk a DRF paginated response, following `next` links, and return the
 * concatenated list of all results.
 */
async function collectPages<T>(
  first: Paginated<T>,
  headers: Record<string, string>,
): Promise<T[]> {
  const all = [...first.results];
  let next = first.next;
  while (next) {
    // `next` is an absolute URL pointing at the API origin. Strip the origin
    // so the request goes through the same dev proxy / same-origin path as the
    // initial call (fetching the backend port directly would fail CORS).
    const path = next.replace(/^https?:\/\/[^/]+/, "");
    const res = await fetch(path, { headers });
    if (!res.ok) break;
    const page = (await res.json()) as Paginated<T>;
    all.push(...page.results);
    next = page.next;
  }
  return all;
}

// Seasons
export function getSeasons() {
  return request<Season[]>("/seasons/");
}

export function createSeason(name: string) {
  return request<Season>("/seasons/", {
    method: "POST",
    body: JSON.stringify({ name }),
  });
}

/** Download the season's task schedule as a CSV file (triggers a browser download). */
export async function exportSeasonCsv(seasonId: number, seasonName: string) {
  return downloadSeasonExport(seasonId, seasonName, "csv");
}

/** Download the season's task schedule as a PDF file (triggers a browser download). */
export async function exportSeasonPdf(seasonId: number, seasonName: string) {
  return downloadSeasonExport(seasonId, seasonName, "pdf");
}

async function downloadSeasonExport(
  seasonId: number,
  seasonName: string,
  format: "csv" | "pdf",
) {
  const token = getToken();
  const res = await fetch(`${API}/seasons/${seasonId}/export_${format}/`, {
    headers: token ? { Authorization: `Token ${token}` } : {},
  });
  if (!res.ok) {
    // Mirror the request() helper: a 401 means the session expired.
    if (res.status === 401) {
      clearAuth();
      window.dispatchEvent(new CustomEvent("auth:logout"));
    }
    throw new Error(`Export failed: ${res.status}`);
  }
  const blob = await res.blob();
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = `schedule_${seasonName}.${format}`;
  document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(url);
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

export function createTeam(data: { name: string; age_category: string }) {
  return request<Team>("/teams/", {
    method: "POST",
    body: JSON.stringify(data),
  });
}

export function updateTeam(
  teamId: number,
  data: Partial<{ name: string; age_category: string }>,
) {
  return request<Team>(`/teams/${teamId}/`, {
    method: "PATCH",
    body: JSON.stringify(data),
  });
}

export function deleteTeam(teamId: number) {
  return request<void>(`/teams/${teamId}/`, { method: "DELETE" });
}

// Players
export function getPlayers() {
  return request<Player[]>("/players/");
}

export function createPlayer(data: {
  first_name: string;
  last_name: string;
  team_id: number;
  is_coach?: boolean;
  coached_teams?: number[];
  referee_certification?: string;
}) {
  return request<Player>("/players/", {
    method: "POST",
    body: JSON.stringify(data),
  });
}

export function updatePlayer(
  playerId: number,
  data: Partial<{
    first_name: string;
    last_name: string;
    team_id: number;
    is_coach: boolean;
    coached_teams: number[];
    referee_certification: string;
  }>,
) {
  return request<Player>(`/players/${playerId}/`, {
    method: "PATCH",
    body: JSON.stringify(data),
  });
}

export function deletePlayer(playerId: number) {
  return request<void>(`/players/${playerId}/`, { method: "DELETE" });
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
  return request<{ teams: number; players_created: number; players_updated: number }>("/players/import_members/", {
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
  game_type: "HOME" | "AWAY";
}) {
  return request<Game>("/games/", {
    method: "POST",
    body: JSON.stringify(data),
  });
}

export function updateGame(
  gameId: number,
  data: Partial<{
    home_team_id: number;
    away_team: string;
    date: string;
    time: string;
    court: string;
    half: string;
    game_type: "HOME" | "AWAY";
  }>,
) {
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

// Settings
export function getTeamSettings() {
  return request<Team[]>("/settings/");
}

export function updateTeamSettings(
  teamId: number,
  data: Partial<Team>,
) {
  return request<Team>(`/settings/${teamId}/`, {
    method: "PUT",
    body: JSON.stringify(data),
  });
}

// Availability
export function getAvailability(season: number) {
  return request<AvailabilityDay[]>(`/availability/?season=${season}`);
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

export function passwordResetRequest(email: string) {
  return request<{ token: string; uid: number }>("/auth/password_reset_request/", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email }),
  });
}

export function passwordResetConfirm(token: string, uid: number, password: string) {
  return request<unknown>("/auth/password_reset_confirm/", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ token, uid, password }),
  });
}

export function verifyEmailRequest() {
  return request<{ token: string }>("/auth/verify_email_request/", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
  });
}

export function verifyEmailConfirm(token: string) {
  return request<unknown>("/auth/verify_email_confirm/", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ token }),
  });
}
