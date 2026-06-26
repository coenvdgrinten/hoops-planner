import { useState, useRef, useEffect } from "react";
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

  const [open, setOpen] = useState(false);
  const containerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const handleClickOutside = (e: MouseEvent) => {
      if (containerRef.current && !containerRef.current.contains(e.target as Node)) {
        setOpen(false);
      }
    };
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape") setOpen(false);
    };
    document.addEventListener("mousedown", handleClickOutside);
    document.addEventListener("keydown", handleKeyDown);
    return () => {
      document.removeEventListener("mousedown", handleClickOutside);
      document.removeEventListener("keydown", handleKeyDown);
    };
  }, []);

  const selectedSeason = seasons.find((s) => s.id === selectedId);

  if (isLoading) return <p>Loading seasons...</p>;
  if (error) return <p className="error">Error: {error.message}</p>;
  if (seasons.length === 0)
    return <p>No seasons yet. Import a schedule to get started.</p>;

  return (
    <div className="season-dropdown" ref={containerRef}>
      <button
        className={`season-dropdown-toggle ${open ? "open" : ""}`}
        onClick={() => setOpen(!open)}
      >
        <span className="season-dropdown-value">
          {selectedSeason ? selectedSeason.name : "Select season"}
        </span>
        <span className={`season-chevron ${open ? "open" : ""}`}>▾</span>
      </button>
      {open && (
        <div className="season-dropdown-menu">
          {seasons.map((s) => (
            <button
              key={s.id}
              className={`season-dropdown-item ${s.id === selectedId ? "selected" : ""}`}
              onClick={() => {
                onSelect(s);
                setOpen(false);
              }}
            >
              <span className="season-dropdown-item-text">{s.name}</span>
              {s.id === selectedId && <span className="season-check">✓</span>}
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
