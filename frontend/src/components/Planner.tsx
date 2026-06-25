import { useCallback } from "react";
import { useQuery } from "@tanstack/react-query";
import { getGames } from "../api";
import type { Season, Game } from "../types";
import type { TaskWithAssignments } from "../types";
import { GameCard } from "./GameCard";

interface Props {
  season: Season;
  onSelectTask: (task: TaskWithAssignments, gameId: number) => void;
}

export function Planner({ season, onSelectTask }: Props) {
  const { data: games = [], isLoading, error } = useQuery({
    queryKey: ["games", season.id],
    queryFn: () => getGames(season.id),
  });

  const handleSelectTask = useCallback(
    (task: TaskWithAssignments, gameId: number) => {
      onSelectTask(task, gameId);
    },
    [onSelectTask]
  );

  if (isLoading) return <p>Loading games...</p>;
  if (error) return <p className="error">Error: {error.message}</p>;
  if (games.length === 0) return <p>No games in this season.</p>;

  // Group games by date, then by court
  const grouped: Record<string, Record<string, Game[]>> = {};
  const sorted = [...games].sort((a, b) => {
    const da = `${a.date}T${a.time}`;
    const db = `${b.date}T${b.time}`;
    return da.localeCompare(db);
  });
  for (const game of sorted) {
    if (!grouped[game.date]) grouped[game.date] = {};
    if (!grouped[game.date][game.court]) grouped[game.date][game.court] = [];
    grouped[game.date][game.court].push(game);
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
        {Object.entries(grouped).map(([date, courts]) => {
          const dateObj = new Date(`${date}T00:00`);
          const formattedDate = dateObj.toLocaleDateString("nl-BE", {
            weekday: "long",
            day: "numeric",
            month: "short",
          });
          const isFuture = dateObj >= new Date(new Date().toISOString().split("T")[0]);
          // Sort courts numerically
          const sortedCourts = Object.entries(courts).sort(([a], [b]) => Number(a) - Number(b));
          return (
            <div key={date} className="date-group">
              <div className="date-label">
                {isFuture && <span className="upcoming-badge">Upcoming Games</span>}
                <span>{formattedDate}</span>
              </div>
              <div className="courts-row">
                {sortedCourts.map(([court, courtGames]) => (
                  <div key={court} className="court-column">
                    <div className="court-header">Court {court}</div>
                    <div className="court-games">
                      {courtGames.map((game) => (
                        <GameCard
                          key={game.id}
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
                ))}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
