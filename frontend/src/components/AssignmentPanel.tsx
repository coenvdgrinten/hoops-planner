import { useMemo, useState, useRef, useEffect } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import type { TaskWithAssignments, Player, CandidateDetail } from "../types";
import {
  createAssignment,
  deleteAssignment,
  getTasksWithAssignments,
  getTeamEligibility,
  getCandidateDetails,
} from "../api";

interface Props {
  task: TaskWithAssignments;
  gameId: number;
  onClose: () => void;
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
  onClose,
}: Props) {
  const [search, setSearch] = useState("");
  const [lastError, setLastError] = useState<string | null>(null);
  const [expandedTeams, setExpandedTeams] = useState<Set<number>>(new Set());
  const queryClient = useQueryClient();
  const prevTaskId = useRef(task.id);

  // Reset search and error when switching to a different task
  useEffect(() => {
    if (task.id !== prevTaskId.current) {
      prevTaskId.current = task.id;
      setSearch("");
      setLastError(null);
    }
  }, [task.id]);

  // Fetch task data — stays in sync after mutations via invalidation
  const { data: currentTask } = useQuery({
    queryKey: ["tasks-with-assignments", gameId],
    queryFn: () => getTasksWithAssignments(gameId),
  });

  const fetchedTask = currentTask?.find((t) => t.id === task.id) ?? task;

  // Fetch team eligibility data
  const { data: teamEligibility = [] } = useQuery({
    queryKey: ["team-eligibility", task.id],
    queryFn: () => getTeamEligibility(task.id),
  });

  // Fetch suggested candidates
  const { data: candidates = [] } = useQuery({
    queryKey: ["candidate-details", task.id],
    queryFn: () => getCandidateDetails(task.id),
  });

  // Assign mutation
  const { mutate: assign, isPending: assigning } = useMutation({
    mutationFn: (player: Player) => createAssignment(task.id, player.id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["tasks-with-assignments", gameId] });
      queryClient.invalidateQueries({ queryKey: ["team-eligibility", task.id] });
    },
    onError: (err) => {
      console.error("Failed to assign player:", err);
      setLastError(err instanceof Error ? err.message : "Assignment failed");
    },
  });

  // Unassign mutation
  const { mutate: unassign } = useMutation({
    mutationFn: (assignmentId: number) => deleteAssignment(assignmentId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["tasks-with-assignments", gameId] });
      queryClient.invalidateQueries({ queryKey: ["team-eligibility", task.id] });
    },
    onError: (err) => {
      console.error("Failed to unassign player:", err);
      setLastError(err instanceof Error ? err.message : "Removal failed");
    },
  });

  // Get assigned player IDs for quick lookup
  const assignedIds = new Set(fetchedTask.assignments.map((a) => a.player.id));

  // Filter teams and players by search query
  const filteredTeams = useMemo(() => {
    if (!search.trim()) return teamEligibility;
    const q = search.toLowerCase();
    return teamEligibility
      .map((t) => ({
        ...t,
        players: t.players.filter((p) =>
          p.player.full_name.toLowerCase().includes(q) ||
          p.player.team.name.toLowerCase().includes(q)
        ),
      }))
      .filter((t) => t.players.length > 0);
  }, [teamEligibility, search]);

  // Toggle team expansion
  const toggleTeam = (teamId: number) => {
    setExpandedTeams((prev) => {
      const next = new Set(prev);
      if (next.has(teamId)) next.delete(teamId);
      else next.add(teamId);
      return next;
    });
  };

  const label = TASK_LABELS[fetchedTask.task_type] ?? fetchedTask.task_type;
  const title = fetchedTask.slot_number > 1 ? `${label} #${fetchedTask.slot_number}` : label;

  return (
    <aside className="assignment-panel">
      <div className="panel-header">
        <div>
          <h3>{title}</h3>
          <p className="panel-subtitle">
            {fetchedTask.assignments.length} assigned
          </p>
        </div>
        <button className="close-btn" onClick={onClose} title="Close">
          ×
        </button>
      </div>
      {lastError && (
        <div className="error-banner">
          <span>{lastError}</span>
          <button className="dismiss-btn" onClick={() => setLastError(null)}>×</button>
        </div>
      )}

      {/* Search */}
      <div className="panel-search">
        <input
          type="text"
          placeholder="Search member or team..."
          value={search}
          onChange={(e) => setSearch(e.target.value)}
        />
      </div>

      {/* Assigned Players */}
      <div className="panel-section">
        <h4>Assigned</h4>
        <div className="assigned-list">
          {fetchedTask.assignments.length === 0 && (
            <p className="empty-msg">No one assigned yet</p>
          )}
          {fetchedTask.assignments.map((a) => (
            <div key={a.id} className="assigned-player">
              <div className="player-info">
                <span className="player-name">{a.player.full_name}</span>
                <span className="player-team">
                  {a.player.team.name}
                </span>
              </div>
              <button
                className="remove-btn"
                onClick={() => unassign(a.id)}
                title="Remove"
              >
                ×
              </button>
            </div>
          ))}
        </div>
      </div>

      {/* Suggested Candidates */}
      <div className="panel-section">
        <h4>Suggested</h4>
        <div className="suggested-list">
          {candidates.length === 0 && (
            <p className="empty-msg">No suggestions available</p>
          )}
          {candidates.map((candidate: CandidateDetail) => {
            const player = candidate.player;
            const isAssigned = assignedIds.has(player.id);
            return (
              <div
                key={player.id}
                className={`suggested-row ${isAssigned ? "assigned" : ""}`}
              >
                <div className="suggested-info">
                  <div className="suggested-avatar">
                    {player.full_name.split(' ').map(n => n[0]).join('').slice(0, 2).toUpperCase()}
                  </div>
                  <div className="suggested-details">
                    <span className="suggested-name">{player.full_name}</span>
                    <span className="suggested-meta">
                      {player.team.name} · {candidate.task_count} task{candidate.task_count !== 1 ? 's' : ''}
                    </span>
                    <span className="suggestion-reason" title={candidate.suggestion_reason}>
                      {candidate.suggestion_reason}
                    </span>
                  </div>
                </div>
                {!isAssigned && (
                  <button
                    className={`add-btn ${isAssigned ? "assigned" : ""}`}
                    onClick={() => assign(player)}
                    disabled={assigning}
                    title="Add"
                  >
                    +
                  </button>
                )}
              </div>
            );
          })}
        </div>
      </div>

      {/* Teams & Members */}
      <div className="panel-section">
        <h4>Teams & Members</h4>
        <div className="teams-list">
          {filteredTeams.length === 0 && (
            <p className="empty-msg">No teams or members found</p>
          )}
          {filteredTeams.map((teamData) => {
            const isExpanded = expandedTeams.has(teamData.team.id);
            const hasEligible = teamData.eligible_count > 0;
            // Determine border color: green (eligible + at gym), orange (eligible + not at gym), red (no eligible)
            let headerClass: string;
            if (!hasEligible) {
              headerClass = "ineligible";
            } else if (!teamData.at_gym_day) {
              headerClass = "not-at-gym";
            } else {
              headerClass = "eligible";
            }
            return (
              <div key={teamData.team.id} className="team-group">
                <button
                  className={`team-header ${headerClass}`}
                  onClick={() => toggleTeam(teamData.team.id)}
                >
                  <span className={`team-chevron ${isExpanded ? "expanded" : ""}`}>▸</span>
                  <span className="team-name">{teamData.team.name}</span>
                  <span className="team-badge" title="Eligible members">
                    {teamData.eligible_count}/{teamData.players.length}
                  </span>
                </button>
                {isExpanded && (
                  <div className="members-list">
                    {teamData.players.map((pData) => {
                      const player = pData.player;
                      const isAssigned = assignedIds.has(player.id);
                      const reason = pData.eligible ? "" : (pData.ineligible_reason || "Not eligible");
                      return (
                        <div
                          key={player.id}
                          className={`member-row ${pData.eligible ? "eligible" : "ineligible"} ${isAssigned ? "assigned" : ""}`}
                          title={reason}
                        >
                          <div className="member-info">
                            <div className="member-avatar">
                              {player.full_name.split(' ').map(n => n[0]).join('').slice(0, 2).toUpperCase()}
                            </div>
                            <div className="member-details">
                              <span className="member-name">{player.full_name}</span>
                              <span className="member-meta">
                                {pData.at_gym === "before" ? "Game before" : pData.at_gym === "after" ? "Game after" : ""}
                              </span>
                            </div>
                          </div>
                          <div className="member-actions">
                            <span className="task-count-badge" title="Task load">
                              {Math.round(pData.task_count)}
                            </span>
                            {!isAssigned && (
                              <button
                                className={`add-btn ${pData.eligible ? "" : "ineligible"}`}
                                onClick={() => assign(player)}
                                disabled={assigning || !pData.eligible}
                                title={pData.eligible ? "Add" : reason}
                              >
                                +
                              </button>
                            )}
                          </div>
                        </div>
                      );
                    })}
                  </div>
                )}
              </div>
            );
          })}
        </div>
      </div>

      <button className="close-panel-btn" onClick={onClose}>
        Close Panel
      </button>
    </aside>
  );
}
