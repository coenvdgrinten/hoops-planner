import { useState, useRef, useEffect } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { getSeasons, createSeason } from "../api";
import type { Season } from "../types";
import styles from "./SeasonSelector.module.css";

interface Props {
  onSelect: (season: Season) => void;
  selectedId?: number;
}

export function SeasonSelector({ onSelect, selectedId }: Props) {
  const queryClient = useQueryClient();
  const { data: seasons = [], isLoading, error } = useQuery({
    queryKey: ["seasons"],
    queryFn: getSeasons,
  });

  const [open, setOpen] = useState(false);
  const [creating, setCreating] = useState(false);
  const [newName, setNewName] = useState("");
  const [createError, setCreateError] = useState<string | null>(null);
  const containerRef = useRef<HTMLDivElement>(null);

  const createMutation = useMutation({
    mutationFn: (name: string) => createSeason(name),
    onSuccess: (season) => {
      queryClient.invalidateQueries({ queryKey: ["seasons"] });
      onSelect(season);
      setCreating(false);
      setNewName("");
      setCreateError(null);
      setOpen(false);
    },
    onError: (err) => {
      setCreateError(err instanceof Error ? err.message : "Failed to create season");
    },
  });

  const handleCreate = (e: React.FormEvent) => {
    e.preventDefault();
    setCreateError(null);
    const name = newName.trim();
    if (!name) {
      setCreateError("Season name is required");
      return;
    }
    createMutation.mutate(name);
  };

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
    return (
      <div className={styles["season-dropdown"]} ref={containerRef}>
        <button
          className={styles["season-dropdown-toggle"]}
          onClick={() => setCreating((c) => !c)}
        >
          <span className={styles["season-dropdown-value"]}>New season</span>
          <span className={styles["season-chevron"]}>＋</span>
        </button>
        {creating && (
          <form className={styles["season-create-form"]} onSubmit={handleCreate}>
            <input
              type="text"
              aria-label="New season name"
              value={newName}
              onChange={(e) => setNewName(e.target.value)}
              placeholder="e.g. 2025-2026"
              autoFocus
            />
            {createError && <p className="error season-create-error">{createError}</p>}
            <div className={styles["season-create-actions"]}>
              <button
                type="submit"
                className="icon-btn"
                disabled={createMutation.isPending}
              >
                {createMutation.isPending ? "Creating..." : "Create"}
              </button>
              <button
                type="button"
                className="icon-btn"
                onClick={() => {
                  setCreating(false);
                  setNewName("");
                  setCreateError(null);
                }}
              >
                Cancel
              </button>
            </div>
          </form>
        )}
      </div>
    );

  return (
    <div className={styles["season-dropdown"]} ref={containerRef}>
      <button
        data-testid="season-dropdown-toggle"
        className={`${styles["season-dropdown-toggle"]} ${open ? styles.open : ""}`}
        onClick={() => setOpen(!open)}
      >
        <span data-testid="season-dropdown-value" className={styles["season-dropdown-value"]}>
          {selectedSeason ? selectedSeason.name : "Select season"}
        </span>
        <span className={`${styles["season-chevron"]} ${open ? styles.open : ""}`}>▾</span>
      </button>
      {open && (
        <div data-testid="season-dropdown-menu" className={styles["season-dropdown-menu"]}>
          {seasons.map((s) => (
            <button
              key={s.id}
              data-testid={`season-dropdown-item-${s.id}`}
              className={`${styles["season-dropdown-item"]} ${s.id === selectedId ? styles.selected : ""}`}
              onClick={() => {
                onSelect(s);
                setOpen(false);
              }}
            >
              <span className={styles["season-dropdown-item-text"]}>{s.name}</span>
              {s.id === selectedId && <span data-testid="season-check" className={styles["season-check"]}>✓</span>}
            </button>
          ))}
          <button
            className={`${styles["season-dropdown-item"]} ${styles["season-dropdown-new"]}`}
            onClick={() => {
              setOpen(false);
              setCreating(true);
            }}
          >
            <span className={styles["season-dropdown-item-text"]}>＋ New season</span>
          </button>
        </div>
      )}
      {creating && (
        <form className={styles["season-create-form"]} onSubmit={handleCreate}>
          <input
            type="text"
            aria-label="New season name"
            value={newName}
            onChange={(e) => setNewName(e.target.value)}
            placeholder="e.g. 2025-2026"
            autoFocus
          />
          {createError && <p className="error season-create-error">{createError}</p>}
          <div className={styles["season-create-actions"]}>
            <button
              type="submit"
              className="icon-btn"
              disabled={createMutation.isPending}
            >
              {createMutation.isPending ? "Creating..." : "Create"}
            </button>
            <button
              type="button"
              className="icon-btn"
              onClick={() => {
                setCreating(false);
                setNewName("");
                setCreateError(null);
              }}
            >
              Cancel
            </button>
          </div>
        </form>
      )}
    </div>
  );
}
