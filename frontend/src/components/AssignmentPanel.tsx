import { useState, useMemo, useCallback } from "react";
import type { TaskWithAssignments, CandidateDetail, Player } from "../types";
import {
  createAssignment,
  deleteAssignment,
} from "../api";

interface Props {
  task: TaskWithAssignments;
  gameId: number;
  suggestions: CandidateDetail[];
  loading: boolean;
  onClose: () => void;
  onReady: (task: TaskWithAssignments, gameId: number) => void;
  onRefresh: (task: TaskWithAssignments, gameId: number) => void;
}

const TASK_LABELS: Record<string, string> = {
  REFEREE: "Referee",
  SCORER: "Scorer",
  TIMER: "Timer",
  SECOND_24_OPERATOR: "24-sec Operator",
};

export function AssignmentPanel({
  task,
  gameId,
  suggestions,
  loading,
  onClose,
  onReady,
  onRefresh,
}: Props) {
  const [search, setSearch] = useState("");
  const [busy, setBusy] = useState(false);

  // Notify parent that panel is ready so it can fetch suggestions
  const handleReady = useCallback(() => {
    if (suggestions.length === 0 && !loading) {
      onReady(task, gameId);
    }
  }, [task, gameId, suggestions, loading, onReady]);

  // Filter candidates by search query
  const filteredSuggestions = useMemo(() => {
    if (!search.trim()) return suggestions;
    const q = search.toLowerCase();
    return suggestions.filter((s) =>
      s.player.full_name.toLowerCase().includes(q)
    );
  }, [suggestions, search]);

  // Get assigned player IDs for quick lookup
  const assignedIds = new Set(task.assignments.map((a) => a.player.id));

  // Filter out already-assigned candidates
  const availableSuggestions = useMemo(() => {
    return filteredSuggestions.filter((s) => !assignedIds.has(s.player.id));
  }, [filteredSuggestions, assignedIds]);

  const label = TASK_LABELS[task.task_type] ?? task.task_type;
  const title = task.slot_number > 1 ? `${label} #${task.slot_number}` : label;

  const handleAssign = async (player: Player) => {
    setBusy(true);
    try {
      await createAssignment(task.id, player.id);
      await onRefresh(task, gameId);
    } catch {
      // Ignore errors
    } finally {
      setBusy(false);
    }
  };

  const handleUnassign = async (assignmentId: number) => {
    setBusy(true);
    try {
      await deleteAssignment(assignmentId);
      await onRefresh(task, gameId);
    } catch {
      // Ignore errors
    } finally {
      setBusy(false);
    }
  };

  return (
    <aside className="assignment-panel">
      <div className="panel-header">
        <div>
          <h3>{title}</h3>
          <p className="panel-subtitle">
            {task.assignments.length} / {task.assignments.length} assigned
          </p>
        </div>
        <button className="close-btn" onClick={onClose} title="Close">
          ×
        </button>
      </div>

      {/* Search */}
      <div className="panel-search">
        <input
          type="text"
          placeholder="Search member or team..."
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          onFocus={handleReady}
        />
      </div>

      {/* Assigned Players */}
      <div className="panel-section">
        <h4>Assigned</h4>
        <div className="assigned-list">
          {task.assignments.length === 0 && (
            <p className="empty-msg">No one assigned yet</p>
          )}
          {task.assignments.map((a) => (
            <div key={a.id} className="assigned-player">
              <div className="player-avatar">{a.player.full_name.charAt(0)}</div>
              <div className="player-info">
                <span className="player-name">{a.player.full_name}</span>
                <span className="player-team">
                  {a.player.team_name || "Unknown team"}
                </span>
              </div>
              <button
                className="remove-btn"
                onClick={() => handleUnassign(a.id)}
                disabled={busy}
                title="Remove"
              >
                ×
              </button>
            </div>
          ))}
        </div>
      </div>

      {/* Candidates */}
      <div className="panel-section">
        <h4>Top Candidates</h4>
        <div className="candidates-list">
          {loading && <p className="empty-msg">Loading candidates...</p>}
          {!loading && availableSuggestions.length === 0 && (
            <p className="empty-msg">No candidates available</p>
          )}
          {availableSuggestions.slice(0, 10).map((s) => (
            <div
              key={s.player.id}
              className="candidate-row"
            >
              <div className="candidate-info">
                <div className="player-avatar">
                  {s.player.full_name.charAt(0)}
                </div>
                <div>
                  <span className="player-name">{s.player.full_name}</span>
                  <span className="player-meta">
                    {s.player.team_name} · Tasks: {Math.round(s.task_count)}
                  </span>
                </div>
              </div>
              <div className="candidate-actions">
                {s.at_gym && <span className="at-gym-badge">AT GYM</span>}
                <button
                  className="add-btn"
                  onClick={() => handleAssign(s.player)}
                  disabled={busy}
                >
                  Add
                </button>
              </div>
            </div>
          ))}
        </div>
      </div>

      <button className="close-panel-btn" onClick={onClose}>
        Close Panel
      </button>
    </aside>
  );
}
