import { useEffect, useState } from "react";
import {
  getTasks,
  getAssignments,
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
  const [tasks, setTasks] = useState<Task[]>([]);
  const [assignments, setAssignments] = useState<Record<number, TaskAssignment[]>>({});
  const [suggestions, setSuggestions] = useState<Record<number, CandidateDetail[]>>({});
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    getTasks(gameId)
      .then((tasks) => {
        setTasks(tasks);
        // Load assignments for each task
        Promise.all(
          tasks.map((t) =>
            getAssignments(t.id).then((asgn) => [t.id, asgn] as const)
          )
        ).then((results) => {
          const map: Record<number, TaskAssignment[]> = {};
          for (const [taskId, asgn] of results) {
            map[taskId] = asgn;
          }
          setAssignments(map);
        });
        // Load candidate details for each task
        Promise.all(
          tasks.map((t) =>
            getCandidateDetails(t.id).then((det) => [t.id, det] as const)
          )
        ).then((results) => {
          const map: Record<number, CandidateDetail[]> = {};
          for (const [taskId, det] of results) {
            map[taskId] = det;
          }
          setSuggestions(map);
        });
      })
      .finally(() => setLoading(false));
  }, [gameId]);

  const handleAssign = async (taskId: number, player: Player) => {
    await createAssignment(taskId, player.id);
    // Refresh assignments
    const asgn = await getAssignments(taskId);
    setAssignments((prev) => ({ ...prev, [taskId]: asgn }));
  };

  const handleUnassign = async (assignmentId: number, taskId: number) => {
    await deleteAssignment(assignmentId);
    const asgn = await getAssignments(taskId);
    setAssignments((prev) => ({ ...prev, [taskId]: asgn }));
  };

  if (loading) return <p>Loading tasks...</p>;

  return (
    <div className="task-grid">
      {tasks.map((task) => {
        const assigned = assignments[task.id] ?? [];
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
