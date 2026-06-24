import { useEffect, useState } from "react";
import {
  getTasksWithAssignments,
  createAssignment,
  deleteAssignment,
  getCandidateDetails,
} from "../api";
import type { Task, TaskAssignment, CandidateDetail, Player } from "../types";

interface Props {
  gameId: number;
}

const TASK_LABELS: Record<string, string> = {
  REFEREE: "Referee",
  SCORER: "Scorer",
  TIMER: "Timer",
  SECOND_24_OPERATOR: "24-sec Operator",
};

export function TaskCard({ gameId }: Props) {
  const [tasks, setTasks] = useState<
    { id: number; task_type: string; slot_number: number; assignments: TaskAssignment[] }[]
  >([]);
  const [suggestions, setSuggestions] = useState<Record<number, CandidateDetail[]>>({});
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    setLoading(true);
    getTasksWithAssignments(gameId)
      .then((data) => {
        setTasks(data);
        // Load candidate details only for unassigned tasks
        const unassigned = data.filter((t) => t.assignments.length === 0);
        if (unassigned.length > 0) {
          Promise.all(
            unassigned.map((t) =>
              getCandidateDetails(t.id).then((det) => [t.id, det] as const)
            )
          ).then((results) => {
            const map: Record<number, CandidateDetail[]> = {};
            for (const [taskId, det] of results) {
              map[taskId] = det;
            }
            setSuggestions(map);
          });
        }
      })
      .finally(() => setLoading(false));
  }, [gameId]);

  const handleAssign = async (taskId: number, player: Player) => {
    await createAssignment(taskId, player.id);
    // Refresh the full task list
    const data = await getTasksWithAssignments(gameId);
    setTasks(data);
    // Remove stale suggestions for this task
    setSuggestions((prev) => {
      const next = { ...prev };
      delete next[taskId];
      return next;
    });
  };

  const handleUnassign = async (assignmentId: number, taskId: number) => {
    await deleteAssignment(assignmentId);
    // Refresh the full task list
    const data = await getTasksWithAssignments(gameId);
    setTasks(data);
    // Load suggestions for this task now that it might be unassigned
    const task = data.find((t) => t.id === taskId);
    if (task && task.assignments.length === 0) {
      const det = await getCandidateDetails(taskId);
      setSuggestions((prev) => ({ ...prev, [taskId]: det }));
    }
  };

  if (loading) return <p>Loading tasks...</p>;

  return (
    <div className="task-grid">
      {tasks.map((task) => {
        const assigned = task.assignments;
        const sugg = suggestions[task.id] ?? [];
        const label = TASK_LABELS[task.task_type] ?? task.task_type;

        return (
          <div key={task.id} className="task-card">
            <h4>
              {label}
              {task.slot_number > 1 ? ` #${task.slot_number}` : ""}
            </h4>
            <div className="assigned-players">
              {assigned.length === 0 && <em className="unassigned">Unassigned</em>}
              {assigned.map((a) => (
                <span key={a.id} className="player-badge">
                  {a.player.full_name}
                  <button
                    onClick={() => handleUnassign(a.id, task.id)}
                    title="Remove"
                  >
                    ×
                  </button>
                </span>
              ))}
            </div>
            {assigned.length === 0 && sugg.length > 0 && (
              <div className="suggestions">
                {sugg.slice(0, 3).map((s) => (
                  <button
                    key={s.player.id}
                    className="suggest-btn"
                    onClick={() => handleAssign(task.id, s.player)}
                    title={`${s.player.full_name} (${s.task_count} tasks${s.at_gym ? ", at gym" : ""})`}
                  >
                    {s.player.full_name}
                    {s.at_gym && <span className="at-gym">📍</span>}
                  </button>
                ))}
              </div>
            )}
          </div>
        );
      })}
    </div>
  );
}
