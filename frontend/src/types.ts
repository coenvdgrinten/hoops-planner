export interface Season {
  id: number;
  name: string;
}

export interface Team {
  id: number;
  name: string;
  age_category: string;
  requires_24_second_operator: boolean;
}

export interface Player {
  id: number;
  first_name: string;
  last_name: string;
  full_name: string;
  team: number;
  team_name: string;
  is_coach: boolean;
  referee_certification: string;
}

export interface Game {
  id: number;
  season: number;
  home_team: Team;
  away_team: string;
  game_type: string;
  date: string;
  time: string;
  court: string;
  required_referees: number;
}

export interface Task {
  id: number;
  game: number;
  task_type: string;
  slot_number: number;
}

export interface TaskAssignment {
  id: number;
  task: number;
  player: Player;
}

export interface EligiblePlayer {
  player: Player;
}

export interface CandidateDetail {
  player: Player;
  task_count: number;
  at_gym: boolean;
}
