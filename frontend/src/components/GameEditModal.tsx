import { useEffect, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { updateGame, deleteGame, getTeams } from "../api";
import type { Game } from "../types";

interface Props {
  game: Game;
  onClose: () => void;
  onSuccess: () => void;
}

export function GameEditModal({ game, onClose, onSuccess }: Props) {
  const queryClient = useQueryClient();
  const [date, setDate] = useState(game.date);
  const [time, setTime] = useState(game.time);
  const [court, setCourt] = useState(game.court);
  const [half, setHalf] = useState(game.half || "1");
  const [awayTeam, setAwayTeam] = useState(game.away_team);
  const [error, setError] = useState<string | null>(null);
  const [showDeleteConfirm, setShowDeleteConfirm] = useState(false);

  const { data: teams = [] } = useQuery({
    queryKey: ["teams"],
    queryFn: getTeams,
  });

  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [onClose]);

  const updateMutation = useMutation({
    mutationFn: () =>
      updateGame(game.id, {
        date,
        time,
        court,
        half,
        away_team: awayTeam,
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["games"] });
      onSuccess();
    },
    onError: (err) => {
      setError(err instanceof Error ? err.message : "Update failed");
    },
  });

  const deleteMutation = useMutation({
    mutationFn: () => deleteGame(game.id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["games"] });
      onSuccess();
    },
    onError: (err) => {
      setError(err instanceof Error ? err.message : "Delete failed");
    },
  });

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    updateMutation.mutate();
  };

  const handleDelete = () => {
    deleteMutation.mutate();
  };

  const isPending = updateMutation.isPending || deleteMutation.isPending;

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div role="dialog" className="modal" onClick={(e) => e.stopPropagation()}>
        <h2>Edit Game</h2>
        <form onSubmit={handleSubmit}>
          <div className="form-group">
            <label>Date:</label>
            <input
              type="date"
              value={date}
              onChange={(e) => setDate(e.target.value)}
              required
            />
          </div>
          <div className="form-group">
            <label>Time:</label>
            <input
              type="time"
              value={time}
              onChange={(e) => setTime(e.target.value)}
              required
            />
          </div>
          <div className="form-row">
            <div className="form-group">
              <label>Court:</label>
              <select
                value={court}
                onChange={(e) => setCourt(e.target.value)}
                required
              >
                <option value="1">Court 1</option>
                <option value="2">Court 2</option>
              </select>
            </div>
            <div className="form-group">
              <label>Half:</label>
              <select
                value={half}
                onChange={(e) => setHalf(e.target.value)}
              >
                <option value="1">First Half</option>
                <option value="2">Second Half</option>
              </select>
            </div>
          </div>
          <div className="form-group">
            <label>Home Team:</label>
            <select
              value={game.home_team.id}
              onChange={() => {
                // Note: home_team_id is write-only in serializer
              }}
              required
            >
              {teams.map((t: { id: number; name: string }) => (
                <option key={t.id} value={t.id}>
                  {t.name}
                </option>
              ))}
            </select>
          </div>
          <div className="form-group">
            <label>Away Team:</label>
            <input
              type="text"
              value={awayTeam}
              onChange={(e) => setAwayTeam(e.target.value)}
              required
            />
          </div>
          {error && <p className="error">{error}</p>}
          <div className="modal-actions">
            {!showDeleteConfirm ? (
              <button
                type="button"
                className="btn-delete"
                onClick={() => setShowDeleteConfirm(true)}
                disabled={isPending}
              >
                Delete
              </button>
            ) : (
              <span className="delete-confirm">
                Really delete?{" "}
                <button type="button" onClick={handleDelete} disabled={isPending}>
                  Yes
                </button>{" "}
                <button type="button" onClick={() => setShowDeleteConfirm(false)}>
                  No
                </button>
              </span>
            )}
            <button type="button" onClick={onClose} disabled={isPending}>
              Cancel
            </button>
            <button type="submit" disabled={isPending}>
              {updateMutation.isPending ? "Saving..." : "Save"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
