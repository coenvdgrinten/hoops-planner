import { useEffect, useState } from "react";
import { getGames } from "../api";
import type { Season, Game } from "../types";
import { GameCard } from "./GameCard";

interface Props {
  season: Season;
}

export function Planner({ season }: Props) {
  const [games, setGames] = useState<Game[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

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

  // Sort by date+time
  const sorted = [...games].sort((a, b) => {
    const da = `${a.date}T${a.time}`;
    const db = `${b.date}T${b.time}`;
    return da.localeCompare(db);
  });

  return (
    <div className="planner">
      <h2>{season.name} — Task Planner</h2>
      <div className="games-list">
        {sorted.map((game) => (
          <GameCard
            key={game.id}
            id={game.id}
            homeTeam={game.home_team}
            awayTeam={game.away_team}
            date={game.date}
            time={game.time}
            court={game.court}
          />
        ))}
      </div>
    </div>
  );
}
