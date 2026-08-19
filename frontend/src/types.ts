export interface Season {
  id: number;
  name: string;
}

export type AgeCategory =
  | "X10"
  | "X12"
  | "X14"
  | "X16"
  | "VSE"
  | "M16"
  | "M18"
  | "M22"
  | "MSE";

export interface Team {
  id: number;
  name: string;
  age_category: AgeCategory;
  required_referees: number;
  optional_referees: number;
  require_scorer: boolean;
  require_timer: boolean;
  requires_24_second_operator: boolean;
  parent_responsible: boolean;
}

export interface Player {
  id: number;
  first_name: string;
  last_name: string;
  full_name: string;
  team: Team;
  is_coach: boolean;
  coached_teams: number[];
  referee_certification: string;
  is_exempt: boolean;
}

export interface Game {
  id: number;
  season: number;
  own_team: Team;
  opponent: string;
  game_type: "HOME" | "AWAY";
  date: string;
  time: string;
  court: string;
  location: string;
  half: string;
}

export interface Task {
  id: number;
  game: number;
  task_type: string;
  slot_number: number;
  optional: boolean;
}

export interface TaskWithAssignments {
  id: number;
  game: number;
  task_type: string;
  slot_number: number;
  optional: boolean;
  assignments: TaskAssignment[];
}

export interface TaskAssignment {
  id: number;
  task: number;
  player: Player;
  assigned_at: string;
  is_parent: boolean;
}

export interface EligiblePlayer {
  id: number;
  first_name: string;
  last_name: string;
  full_name: string;
  is_coach: boolean;
  team: string;
  eligible: boolean;
}

export interface CandidateDetail {
  player: Player;
  task_count: number;
  at_gym: "before" | "after" | null;
  suggestion_reason: string;
}

export interface TeamPlayerEligibility {
  player: Player;
  eligible: boolean;
  ineligible_reason: string | null;
  task_count: number;
  at_gym: "before" | "after" | null;
}

export interface TeamEligibility {
  team: Team;
  players: TeamPlayerEligibility[];
  eligible_count: number;
  at_gym_day: boolean;
}

export interface UpcomingAssignment {
  game_date: string;
  game_time: string;
  own_team: string;
  opponent: string;
  court: string;
  task_type: string;
  slot_number: number;
}

export interface SeasonStats {
  total_games: number;
  total_task_slots: number;
  total_assignments: number;
  fill_rate: number;
  by_task_type: Record<string, { slots: number; filled: number }>;
  per_team: Record<string, { games: number; assignments: number }>;
}

export interface LeaderboardEntry {
  player_id: number;
  player_name: string;
  team: string;
  total_tasks: number;
  effective_tasks: number;
  away_day_tasks: number;
  away_day_bonus: number;
  by_type: Record<string, number>;
}

export interface AvailabilityMember {
  id: number;
  name: string;
  is_coach: boolean;
}

export interface AvailabilityAwayGame {
  game_id: number;
  team: Team;
  opponent: string;
  time: string;
  member_count: number;
  members: AvailabilityMember[];
}

export interface AvailabilityDay {
  date: string;
  away_games: AvailabilityAwayGame[];
}
