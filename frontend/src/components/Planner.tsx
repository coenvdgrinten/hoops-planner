import { useCallback, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { getGames } from "../api";
import type { Season, Game } from "../types";
import type { TaskWithAssignments } from "../types";
import { GameCard } from "./GameCard";
import { GameEditModal } from "./GameEditModal";

interface Props {
  season: Season;
  onSelectTask: (task: TaskWithAssignments, gameId: number) => void;
}

export function Planner({ season, onSelectTask }: Props) {
  const [editingGame, setEditingGame] = useState<number | null>(null);
  const [showCreateModal, setShowCreateModal] = useState(false);

  const { data: games = [], isLoading, error } = useQuery({
    queryKey: ["games", season.id],
    queryFn: () => getGames(season.id),
  });

  const editingGameData = editingGame !== null ? games.find((g) => g.id === editingGame) : null;

  const handleSelectTask = useCallback(
    (task: TaskWithAssignments, gameId: number) => {
      onSelectTask(task, gameId);
    },
    [onSelectTask]
  );

  const handleEditGame = useCallback((gameId: number) => {
    setEditingGame(gameId);
  }, []);

  const handleEditClose = useCallback(() => {
    setEditingGame(null);
  }, []);

  const handleCreateClose = useCallback(() => {
    setShowCreateModal(false);
  }, []);

  if (isLoading) return <p>Loading games...</p>;
  if (error) return <p className="error">Error: {error.message}</p>;
  const hasGames = games.length > 0;

  // Group games by half, then by date, then by court
  const grouped: Record<string, Record<string, Record<string, Game[]>>> = {};
  const sorted = [...games].sort((a, b) => {
    const ha = a.half || "1";
    const hb = b.half || "1";
    if (ha !== hb) return ha.localeCompare(hb);
    const da = `${a.date}T${a.time}`;
    const db = `${b.date}T${b.time}`;
    return da.localeCompare(db);
  });
  for (const game of sorted) {
    const h = game.half || "1";
    const d = game.date || "";
    const c = game.court || "1";
    if (!grouped[h]) grouped[h] = {};
    if (!grouped[h][d]) grouped[h][d] = {};
    if (!grouped[h][d][c]) grouped[h][d][c] = [];
    grouped[h][d][c].push(game);
  }

  return (
    <div className="planner">
      <div className="planner-header">
        <div>
          <h2>Game Schedule</h2>
          <p className="planner-subtitle">
            Assign members to standard tasks like refereeing, scoring, and timing.
          </p>
        </div>
        <button className="btn-add-game" onClick={() => setShowCreateModal(true)}>
          + Add Game
        </button>
      </div>
      {hasGames ? (
        <div className="games-by-date">
        {Object.entries(grouped).map(([halfKey, dates]) => {
          const halfLabel = halfKey === "1" ? "First Half" : "Second Half";
          return (
            <div key={halfKey} className="half-group">
              <div className="half-label">{halfLabel}</div>
              {Object.entries(dates).map(([date, courts]) => {
                const dateObj = new Date(`${date || "1970-01-01"}T00:00`);
                const formattedDate = dateObj.toLocaleDateString("nl-BE", {
                  weekday: "long",
                  day: "numeric",
                  month: "short",
                });
                const today = new Date();
                today.setHours(0, 0, 0, 0);
                const isFuture = dateObj >= today;
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
                                half={game.half}
                                onSelectTask={handleSelectTask}
                                onEditGame={handleEditGame}
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
          );
        })}
        </div>
      ) : (
        <p>No games in this season yet. Click "+ Add Game" to create one.</p>
      )}
      {editingGameData && (
        <GameEditModal
          game={editingGameData}
          seasonId={season.id}
          onClose={handleEditClose}
          onSuccess={handleEditClose}
        />
      )}
      {showCreateModal && (
        <GameEditModal
          seasonId={season.id}
          onClose={handleCreateClose}
          onSuccess={handleCreateClose}
        />
      )}
    </div>
  );
}
