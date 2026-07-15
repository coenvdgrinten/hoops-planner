import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { getSeasonStats, getLeaderboard } from "../api";
import type { Season } from "../types";
import styles from "./Statistics.module.css";

interface Props {
  season: Season;
}

const TASK_LABELS: Record<string, string> = {
  REFEREE: "Referee",
  SCORER: "Scorer",
  TIMER: "Timer",
  SECOND_24_OPERATOR: "24-sec Operator",
};

export function Statistics({ season }: Props) {
  const [half, setHalf] = useState<string>("");

  const { data: stats, isLoading: statsLoading, error: statsError } = useQuery({
    queryKey: ["season-stats", season.id, half],
    queryFn: () => getSeasonStats(season.id, half || undefined),
  });

  const { data: leaderboard = [], isLoading: lbLoading, error: lbError } = useQuery({
    queryKey: ["leaderboard", season.id, half],
    queryFn: () => getLeaderboard(season.id, half || undefined),
  });

  const loading = statsLoading || lbLoading;
  const error = statsError ?? lbError;

  if (loading) return <p>Loading statistics...</p>;
  if (error) return <p className="error">Error: {error.message}</p>;
  if (!stats) return <p>No statistics available.</p>;

  return (
    <div className={styles.statistics}>
      <div className={styles["statistics-header"]}>
        <h2>{season.name} — Statistics</h2>
        <div className={styles["half-filter"]}>
          <label htmlFor="half-select">Half:</label>
          <select
            id="half-select"
            value={half}
            onChange={(e) => setHalf(e.target.value)}
          >
            <option value="">Full Season</option>
            <option value="1">First Half</option>
            <option value="2">Second Half</option>
          </select>
        </div>
      </div>

      {/* Overview Cards */}
      <div className={styles["stat-cards"]}>
        <div className={styles["stat-card"]}>
          <span className={styles["stat-value"]}>{stats.total_games}</span>
          <span className={styles["stat-label"]}>Games</span>
        </div>
        <div className={styles["stat-card"]}>
          <span className={styles["stat-value"]}>{stats.total_assignments}/{stats.total_task_slots}</span>
          <span className={styles["stat-label"]}>Tasks Filled</span>
        </div>
        <div className={styles["stat-card"]}>
          <span className={styles["stat-value"]}>{stats.fill_rate}%</span>
          <span className={styles["stat-label"]}>Fill Rate</span>
        </div>
      </div>

      {/* Task Type Breakdown */}
      <div className={styles["stat-section"]}>
        <h3>By Task Type</h3>
        <table>
          <thead>
            <tr>
              <th>Task</th>
              <th>Slots</th>
              <th>Filled</th>
              <th>Fill Rate</th>
            </tr>
          </thead>
          <tbody>
            {Object.entries(stats.by_task_type).map(([type, data]) => {
              const rate = data.slots > 0
                ? Math.round((data.filled / data.slots) * 100)
                : 0;
              return (
                <tr key={type}>
                  <td>{TASK_LABELS[type] ?? type}</td>
                  <td>{data.slots}</td>
                  <td>{data.filled}</td>
                  <td>{rate}%</td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>

      {/* Leaderboard */}
      {leaderboard.length > 0 && (
        <div className={styles["stat-section"]}>
          <h3>Top Contributors</h3>
          <table>
            <thead>
              <tr>
                <th>#</th>
                <th>Player</th>
                <th>Team</th>
                <th>Tasks</th>
                <th>Effective</th>
              </tr>
            </thead>
            <tbody>
              {leaderboard.map((entry, idx) => (
                <tr key={entry.player_id}>
                  <td>{idx + 1}</td>
                  <td>{entry.player_name}</td>
                  <td>{entry.team}</td>
                  <td>{entry.total_tasks}</td>
                  <td>{entry.effective_tasks}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
