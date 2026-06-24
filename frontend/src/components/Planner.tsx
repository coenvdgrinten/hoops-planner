import { useEffect, useState, useCallback } from "react";
import { getGames } from "../api";
import type { Season, Game } from "../types";
import type { TaskWithAssignments } from "../types";
import { GameCard } from "./GameCard";

interface Props {
  season: Season;
  onSelectTask: (task: TaskWithAssignments, gameId: number) => void;
  gameRefreshKey?: number;
}

export function Planner({ season, onSelectTask, gameRefreshKey }: Props) {
  const [games, setGames] = useState<Game[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const handleSelectTask = useCallback(
    (task: TaskWithAssignments, gameId: number) => {
      onSelectTask(task, gameId);
    },
    [onSelectTask]
  );

  useEffect(() => {
    setLoading(true);
    getGames(season.id)
      .then(setGames)
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  }, [season.id]);

  if (loading) return <p>Loading games...</p>;
  if (error) return <p className="error">Error: {error}</p>;
  if (games.length === 0) return <p>No games in this season.</p>;

  // Group games by date
  const grouped: Record<string, Game[]> = {};
  const sorted = [...games].sort((a, b) => {
    const da = `${a.date}T${a.time}`;
    const db = `${b.date}T${b.time}`;
    return da.localeCompare(db);
  });
  for (const game of sorted) {
    if (!grouped[game.date]) grouped[game.date] = [];
    grouped[game.date].push(game);
  }

  return (
    <div className="planner">
      <div className="planner-header">
        <h2>Game Schedule</h2>
        <p className="planner-subtitle">
          Assign members to standard tasks like refereeing, scoring, and timing.
        </p>
      </div>
      <div className="games-by-date">
        {Object.entries(grouped).map(([date, dayGames]) => {
          const dateObj = new Date(`${date}T00:00`);
          const formattedDate = dateObj.toLocaleDateString("nl-BE", {
            weekday: "long",
            day: "numeric",
            month: "short",
          });
          return (
            <div key={date} className="date-group">
              <div className="date-label">
                <span className="upcoming-badge">Upcoming Games</span>
                <span>{formattedDate}</span>
              </div>
              <div className="games-list">
                {dayGames.map((game) => (
                  <GameCard
                    key={`${game.id}-${gameRefreshKey ?? 0}`}
                    id={game.id}
                    homeTeam={game.home_team}
                    awayTeam={game.away_team}
                    date={game.date}
                    time={game.time}
                    court={game.court}
                    onSelectTask={handleSelectTask}
                  />
                ))}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
