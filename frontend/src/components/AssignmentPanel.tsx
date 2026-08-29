import { useCallback, useMemo, useState, useRef, useEffect } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import type { TaskWithAssignments, Player, CandidateDetail, TaskAssignment } from "../types";
import {
  createAssignment,
  deleteAssignment,
  getTasksWithAssignments,
  getTeamEligibility,
  getCandidateDetails,
} from "../api";
import styles from "./AssignmentPanel.module.css";

interface Props {
  task: TaskWithAssignments | undefined;
  gameId: number | undefined;
  open: boolean;
  onClose: () => void;
}

const TASK_LABELS: Record<string, string> = {
  REFEREE: "Referee",
  SCORER: "Scorer",
  TIMER: "Timer",
  ["24_SECOND_OPERATOR"]: "24-sec Operator",
};

export function AssignmentPanel({
  task,
  gameId,
  open,
  onClose,
}: Props) {
  const [search, setSearch] = useState("");
  const [lastError, setLastError] = useState<string | null>(null);
  const [expandedTeams, setExpandedTeams] = useState<Set<number>>(new Set());
  const [toast, setToast] = useState<{ msg: string; assignment: TaskAssignment } | null>(null);
  const toastTimer = useRef<ReturnType<typeof setTimeout>>(undefined);
  const queryClient = useQueryClient();
  const prevTaskId = useRef<number | undefined>(undefined);

  const showToast = useCallback((msg: string, assignment: TaskAssignment) => {
    clearTimeout(toastTimer.current);
    setToast({ msg, assignment });
    toastTimer.current = setTimeout(() => setToast(null), 5000);
  }, []);

  const handleUndo = useCallback(async () => {
    if (!toast) return;
    await deleteAssignment(toast.assignment.id);
    queryClient.invalidateQueries({ queryKey: ["tasks-with-assignments", gameId] });
    queryClient.invalidateQueries({ queryKey: ["team-eligibility", task?.id] });
    queryClient.invalidateQueries({ queryKey: ["season-stats"] });
    setToast(null);
  }, [toast, queryClient, gameId, task?.id]);

  // Reset search and error when switching to a different task
  useEffect(() => {
    if (task?.id !== prevTaskId.current) {
      prevTaskId.current = task?.id;
      setSearch("");
      setLastError(null);
    }
  }, [task?.id]);

  // Fetch task data — stays in sync after mutations via invalidation
  const { data: currentTask } = useQuery({
    queryKey: ["tasks-with-assignments", gameId],
    queryFn: () => getTasksWithAssignments(gameId!),
    enabled: open && !!gameId,
  });

  const fetchedTask = currentTask?.find((t) => t.id === task?.id) ?? task;

  // Fetch team eligibility data
  const { data: teamEligibility = [] } = useQuery({
    queryKey: ["team-eligibility", task?.id],
    queryFn: () => getTeamEligibility(task!.id),
    enabled: open && !!task?.id,
  });

  // Fetch suggested candidates
  const { data: candidates = [] } = useQuery({
    queryKey: ["candidate-details", task?.id],
    queryFn: () => getCandidateDetails(task!.id),
    enabled: open && !!task?.id,
  });

  // Assign mutation
  const { mutate: assign, isPending: assigning } = useMutation({
    mutationFn: (player: Player) => createAssignment(task!.id, player.id),
    onSuccess: (assignment, player) => {
      queryClient.invalidateQueries({ queryKey: ["tasks-with-assignments", gameId] });
      queryClient.invalidateQueries({ queryKey: ["team-eligibility", task?.id] });
      queryClient.invalidateQueries({ queryKey: ["season-stats"] });
      const label = TASK_LABELS[fetchedTask?.task_type ?? ""] ?? fetchedTask?.task_type ?? "";
      showToast(`${player.full_name} assigned as ${label}`, assignment);
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
      queryClient.invalidateQueries({ queryKey: ["team-eligibility", task?.id] });
      queryClient.invalidateQueries({ queryKey: ["season-stats"] });
    },
    onError: (err) => {
      console.error("Failed to unassign player:", err);
      setLastError(err instanceof Error ? err.message : "Removal failed");
    },
  });

  // Get assigned player IDs for quick lookup
  const assignedIds = new Set((fetchedTask?.assignments ?? []).map((a) => a.player.id));

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

  const label = TASK_LABELS[fetchedTask?.task_type ?? ""] ?? fetchedTask?.task_type ?? "";
  const title = fetchedTask && fetchedTask.slot_number > 1 ? `${label} #${fetchedTask.slot_number}` : label;

  // Hide panel when not open (keeps component mounted so cache persists)
  return (
    <aside
      data-testid="assignment-panel"
      className={styles["assignment-panel"]}
      style={{ display: open ? undefined : "none" }}
    >
      <div className={styles["panel-header"]}>
        <div>
          <h3>{title}</h3>
          <p className={styles["panel-subtitle"]}>
            {fetchedTask?.assignments.length ?? 0} assigned
          </p>
        </div>
        <button data-testid="assignment-panel-close" className={styles["close-btn"]} onClick={onClose} title="Close">
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
      <div className={styles["panel-search"]}>
        <input
          type="text"
          aria-label="Search member or team"
          placeholder="Search member or team..."
          value={search}
          onChange={(e) => setSearch(e.target.value)}
        />
      </div>

      {/* Assigned Players */}
      <div className={styles["panel-section"]}>
        <h4>Assigned</h4>
        <div className={styles["assigned-list"]}>
          {fetchedTask?.assignments.length === 0 && (
            <p className={styles["empty-msg"]}>No one assigned yet</p>
          )}
          {fetchedTask?.assignments.map((a) => {
            const displayName = a.is_parent
              ? `Ouder van ${a.player.first_name} ${a.player.last_name}`
              : a.player.full_name;
            return (
              <div key={a.id} className={styles["assigned-player"]}>
                <div className={styles["player-info"]}>
                  <span className={styles["player-name"]}>{displayName}</span>
                  <span className={styles["player-team"]}>
                    {a.player.team.name}
                  </span>
                </div>
                {a.effective_value != null && (
                  <span
                    data-testid={`effective-value-${a.id}`}
                    className={`${styles["effective-badge"]} ${
                      a.effective_value > 1 ? styles["effective-away"] : ""
                    }`}
                    title={
                      a.effective_value > 1
                        ? `Counts double toward ${a.player.full_name}'s effective total (away day)`
                        : `Counts once toward ${a.player.full_name}'s effective total`
                    }
                  >
                    +{a.effective_value}
                    {a.effective_value > 1 && "×"}
                  </span>
                )}
                <button
                  className={styles["remove-btn"]}
                  onClick={() => unassign(a.id)}
                  title="Remove"
                >
                  ×
                </button>
              </div>
            );
          })}
        </div>
      </div>

      {/* Suggested Candidates */}
      <div className={styles["panel-section"]}>
        <h4>Suggested</h4>
        <div className={styles["suggested-list"]}>
          {candidates.length === 0 && (
            <p className={styles["empty-msg"]}>No suggestions available</p>
          )}
          {candidates.map((candidate: CandidateDetail) => {
            const player = candidate.player;
            const isAssigned = assignedIds.has(player.id);
            return (
              <div
                key={player.id}
                className={`${styles["suggested-row"]} ${isAssigned ? styles.assigned : ""}`}
              >
                <div className={styles["suggested-info"]}>
                  <div className={styles["suggested-avatar"]}>
                    {player.full_name.split(' ').map(n => n[0]).join('').slice(0, 2).toUpperCase()}
                  </div>
                  <div className={styles["suggested-details"]}>
                    <span className={styles["suggested-name"]}>
                      {player.full_name}
                      {candidate.has_other_task_same_day && (
                        <span
                          className={styles["sameday-dot"]}
                          title="Already has another task this day"
                        />
                      )}
                    </span>
                    <span className={styles["suggested-meta"]}>
                      {player.team.name} · {candidate.task_count} task{candidate.task_count !== 1 ? 's' : ''}
                    </span>
                    <span className={styles["suggestion-reason"]} title={candidate.suggestion_reason}>
                      {candidate.suggestion_reason}
                    </span>
                  </div>
                </div>
                {!isAssigned && (
                  <button
                    data-testid={`add-candidate-${player.id}`}
                    className={`${styles["add-btn"]} ${isAssigned ? styles.assigned : ""}`}
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
      <div className={styles["panel-section"]}>
        <h4>Teams & Members</h4>
        <div className={styles["teams-list"]}>
          {filteredTeams.length === 0 && (
            <p className={styles["empty-msg"]}>No teams or members found</p>
          )}
          {filteredTeams.map((teamData) => {
            const isExpanded = expandedTeams.has(teamData.team.id);
            const hasEligible = teamData.eligible_count > 0;
            // Determine border color: green (eligible + at gym), orange (eligible + not at gym), red (no eligible)
            let headerClass: string;
            if (!hasEligible) {
              headerClass = String(styles.ineligible);
            } else if (!teamData.at_gym_day) {
              headerClass = String(styles["not-at-gym"]);
            } else {
              headerClass = String(styles.eligible);
            }
            return (
              <div key={teamData.team.id} className={styles["team-group"]}>
                <button
                  className={`${styles["team-header"]} ${headerClass}`}
                  onClick={() => toggleTeam(teamData.team.id)}
                >
                  <span className={`${styles["team-chevron"]} ${isExpanded ? styles.expanded : ""}`}>▸</span>
                  <span className={styles["team-name"]}>{teamData.team.name}</span>
                  <span className={styles["team-badge"]} title="Total assigned tasks (season)">
                    {teamData.total_tasks}T
                  </span>
                  <span className={styles["team-badge"]} title="Eligible members">
                    {teamData.eligible_count}/{teamData.players.length}
                  </span>
                </button>
                {isExpanded && (
                  <div className={styles["members-list"]}>
                    {teamData.players.map((pData) => {
                      const player = pData.player;
                      const isAssigned = assignedIds.has(player.id);
                      const reason = pData.eligible ? "" : (pData.ineligible_reason || "Not eligible");
                      return (
                        <div
                          key={player.id}
                          className={`${styles["member-row"]} ${pData.eligible ? styles.eligible : styles.ineligible} ${isAssigned ? styles.assigned : ""}`}
                          title={reason}
                        >
                          <div className={styles["member-info"]}>
                            <div className={styles["member-avatar"]}>
                              {player.full_name.split(' ').map(n => n[0]).join('').slice(0, 2).toUpperCase()}
                            </div>
                            <div className={styles["member-details"]}>
                              <span className={styles["member-name"]}>
                                {player.full_name}
                                {pData.has_other_task_same_day && (
                                  <span
                                    className={styles["sameday-dot"]}
                                    title="Already has another task this day"
                                  />
                                )}
                              </span>
                              <span className={styles["member-meta"]}>
                                {pData.at_gym === "before" ? "Game before" : pData.at_gym === "after" ? "Game after" : ""}
                              </span>
                            </div>
                          </div>
                          <div className={styles["member-actions"]}>
                            <span className={styles["task-count-badge"]} title="Task load">
                              {Math.round(pData.task_count)}
                            </span>
                            {!isAssigned && (
                              <button
                                className={`${styles["add-btn"]} ${pData.eligible ? "" : styles.ineligible}`}
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

      {toast && (
        <div className={styles["toast"]} data-testid="assignment-toast">
          <span>{toast.msg}</span>
          <button onClick={() => void handleUndo()}>Undo</button>
        </div>
      )}
    </aside>
  );
}
