import { useEffect, useState } from "react";
import { getSeasons } from "../api";
import type { Season } from "../types";

interface Props {
  onSelect: (season: Season) => void;
  selectedId?: number;
}

export function SeasonSelector({ onSelect, selectedId }: Props) {
  const [seasons, setSeasons] = useState<Season[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    getSeasons()
      .then(setSeasons)
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  }, []);

  if (loading) return <p>Loading seasons...</p>;
  if (error) return <p className="error">Error: {error}</p>;
  if (seasons.length === 0)
    return <p>No seasons yet. Import a schedule to get started.</p>;

  return (
    <select
      value={selectedId ?? ""}
      onChange={(e) => {
        const season = seasons.find((s) => s.id === Number(e.target.value));
        if (season) onSelect(season);
      }}
    >
      <option value="">Select a season...</option>
      {seasons.map((s) => (
        <option key={s.id} value={s.id}>
          {s.name}
        </option>
      ))}
    </select>
  );
}
