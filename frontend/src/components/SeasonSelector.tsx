import { useQuery } from "@tanstack/react-query";
import { getSeasons } from "../api";
import type { Season } from "../types";

interface Props {
  onSelect: (season: Season) => void;
  selectedId?: number;
}

export function SeasonSelector({ onSelect, selectedId }: Props) {
  const { data: seasons = [], isLoading, error } = useQuery({
    queryKey: ["seasons"],
    queryFn: getSeasons,
  });

  if (isLoading) return <p>Loading seasons...</p>;
  if (error) return <p className="error">Error: {error.message}</p>;
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
