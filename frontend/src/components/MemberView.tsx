import { useEffect, useState } from "react";
import { getPlayers, getPlayerUpcoming } from "../api";
import type { Player, UpcomingAssignment } from "../types";

const TASK_LABELS: Record<string, string> = {
  REFEREE: "Referee",
  SCORER: "Scorer",
  TIMER: "Timer",
  SECOND_24_OPERATOR: "24-sec Operator",
};

export function MemberView() {
  const [players, setPlayers] = useState<Player[]>([]);
  const [selectedPlayer, setSelectedPlayer] = useState<Player | null>(null);
  const [assignments, setAssignments] = useState<UpcomingAssignment[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    getPlayers()
      .then((p) => setPlayers(p.filter((pl) => !pl.is_coach)))
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  }, []);

  useEffect(() => {
    if (!selectedPlayer) return;
    getPlayerUpcoming(selectedPlayer.id)
      .then(setAssignments)
      .catch((e) => setError(e.message));
  }, [selectedPlayer]);

  if (loading) return <p>Loading members...</p>;
  if (error) return <p className="error">Error: {error}</p>;

  return (
    <div className="member-view">
      <h2>Member View</h2>
      <select
        value={selectedPlayer?.id ?? ""}
        onChange={(e) => {
          const player = players.find((p) => p.id === Number(e.target.value));
          if (player) setSelectedPlayer(player);
        }}
      >
        <option value="">Select a member...</option>
        {players.map((p) => (
          <option key={p.id} value={p.id}>
            {p.full_name} ({p.team_name})
          </option>
        ))}
      </select>

      {selectedPlayer && (
        <div className="member-details">
          <h3>{selectedPlayer.full_name} — Upcoming Assignments</h3>
          {assignments.length === 0 ? (
            <p className="no-assignments">No upcoming assignments.</p>
          ) : (
            <table>
              <thead>
                <tr>
                  <th>Date</th>
                  <th>Time</th>
                  <th>Match</th>
                  <th>Court</th>
                  <th>Task</th>
                </tr>
              </thead>
              <tbody>
                {assignments.map((a, idx) => {
                  const dateObj = new Date(a.game_date);
                  const formattedDate = dateObj.toLocaleDateString("nl-BE", {
                    weekday: "short",
                    day: "numeric",
                    month: "short",
                  });
                  return (
                    <tr key={idx}>
                      <td>{formattedDate}</td>
                      <td>{a.game_time}</td>
                      <td>
                        {a.home_team} vs {a.away_team}
                      </td>
                      <td>{a.court}</td>
                      <td>
                        {TASK_LABELS[a.task_type] ?? a.task_type}
                        {a.slot_number > 1 && ` #${a.slot_number}`}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          )}
        </div>
      )}
    </div>
  );
}
