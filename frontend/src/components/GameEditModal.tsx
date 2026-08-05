import { useEffect, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { createGame, updateGame, deleteGame, getTeams } from "../api";
import type { Game } from "../types";
import styles from "./GameEditModal.module.css";

interface Props {
  game?: Game; // Optional — if missing, operate in create mode
  seasonId: number;
  onClose: () => void;
  onSuccess: () => void;
}

export function GameEditModal({ game, seasonId, onClose, onSuccess }: Props) {
  const queryClient = useQueryClient();
  const isCreateMode = !game;
  const isAway = game?.game_type === "AWAY";
  const [gameType, setGameType] = useState<"HOME" | "AWAY">(isAway ? "AWAY" : "HOME");

  const [date, setDate] = useState(game?.date || "");
  const [time, setTime] = useState(game?.time || "");
  const [court, setCourt] = useState(game?.court || "1");
  const [location, setLocation] = useState(game?.location || "Den Ekkerman");
  const [half, setHalf] = useState(game?.half || "1");
  const [homeTeamId, setHomeTeamId] = useState(game?.home_team.id || 0);
  const [awayTeam, setAwayTeam] = useState(game?.away_team || "");
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

  const createMutation = useMutation({
    mutationFn: () =>
      createGame({
        season: seasonId,
        home_team_id: homeTeamId,
        away_team: awayTeam,
        date,
        time,
        court,
        location,
        half,
        game_type: gameType,
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["games"] });
      onSuccess();
    },
    onError: (err) => {
      setError(err instanceof Error ? err.message : "Create failed");
    },
  });

  const updateMutation = useMutation({
    mutationFn: () =>
      updateGame(game!.id, {
        home_team_id: homeTeamId,
        date,
        time,
        court,
        location,
        half,
        away_team: awayTeam,
        game_type: gameType,
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
    mutationFn: () => deleteGame(game!.id),
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
    if (isCreateMode) {
      createMutation.mutate();
    } else {
      updateMutation.mutate();
    }
  };

  const handleDelete = () => {
    deleteMutation.mutate();
  };

  const isPending = createMutation.isPending || updateMutation.isPending || deleteMutation.isPending;

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div role="dialog" className="modal" onClick={(e) => e.stopPropagation()}>
        <h2>{isCreateMode ? "Add Game" : "Edit Game"}</h2>
        <form onSubmit={handleSubmit}>
          {isCreateMode && (
            <div className="form-group">
              <label>Game Type:</label>
              <select
                value={gameType}
                onChange={(e) => setGameType(e.target.value as "HOME" | "AWAY")}
              >
                <option value="HOME">Home</option>
                <option value="AWAY">Away</option>
              </select>
            </div>
          )}
          {isCreateMode && (
            <div className="form-group">
              <label>Home Team:</label>
              <select
                value={homeTeamId}
                onChange={(e) => setHomeTeamId(Number(e.target.value))}
                required
              >
                <option value={0}>Select a team...</option>
                {teams.map((t: { id: number; name: string }) => (
                  <option key={t.id} value={t.id}>
                    {t.name}
                  </option>
                ))}
              </select>
            </div>
          )}
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
          {gameType === "HOME" && (
            <div className={styles["form-row"]}>
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
                <label>Location:</label>
                <input
                  type="text"
                  value={location}
                  onChange={(e) => setLocation(e.target.value)}
                  placeholder="Den Ekkerman"
                />
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
          )}
          {!isCreateMode && (
            <div className="form-group">
              <label>Home Team:</label>
              <select
                value={homeTeamId}
                onChange={(e) => setHomeTeamId(Number(e.target.value))}
                required
              >
                <option value={0}>Select a team...</option>
                {teams.map((t: { id: number; name: string }) => (
                  <option key={t.id} value={t.id}>
                    {t.name}
                  </option>
                ))}
              </select>
            </div>
          )}
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
            {!isCreateMode && !showDeleteConfirm && (
              <button
                type="button"
                className={styles["btn-delete"]}
                onClick={() => setShowDeleteConfirm(true)}
                disabled={isPending}
              >
                Delete
              </button>
            )}
            {!isCreateMode && showDeleteConfirm && (
              <span className={styles["delete-confirm"]}>
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
              {isCreateMode
                ? createMutation.isPending
                  ? "Creating..."
                  : "Create"
                : updateMutation.isPending
                  ? "Saving..."
                  : "Save"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
