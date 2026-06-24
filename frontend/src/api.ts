import type {
  CandidateDetail,
  EligiblePlayer,
  Game,
  Player,
  Season,
  Task,
  TaskAssignment,
  Team,
} from "./types";

const API = "/api";

async function request<T>(url: string, options?: RequestInit): Promise<T> {
  const res = await fetch(`${API}${url}`, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  if (!res.ok) {
    const text = await res.text();
    throw new Error(`Request failed (${res.status}): ${text}`);
  }
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

export function getEligiblePlayers(task: number) {
  return request<EligiblePlayer[]>(`/players/eligible/?task=${task}`);
}

export function getSuggestions(task: number) {
  return request<Player[]>(`/tasks/${task}/suggestions/`);
}

export function getCandidateDetails(task: number) {
  return request<CandidateDetail[]>(`/tasks/${task}/candidate_details/`);
}

// Task Assignments
export function getAssignments(task: number) {
  return request<TaskAssignment[]>(`/assignments/?task=${task}`);
}

export function createAssignment(task: number, playerId: number) {
  return request<TaskAssignment>(`/assignments/`, {
    method: "POST",
    body: JSON.stringify({ task, player: playerId }),
  });
}

export function deleteAssignment(id: number) {
  return request<void>(`/assignments/${id}/`, { method: "DELETE" });
}
