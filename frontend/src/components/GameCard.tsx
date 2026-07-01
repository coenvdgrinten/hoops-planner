import { useCallback } from "react";
import { useQuery } from "@tanstack/react-query";
import { getTasksWithAssignments } from "../api";
import type { TaskWithAssignments } from "../types";

interface Team {
  name: string;
  age_category: string;
}

interface Props {
  id: number;
  homeTeam: Team;
  awayTeam: string;
  date: string;
  time: string;
  court: string;
  half?: string;
  onSelectTask: (task: TaskWithAssignments, gameId: number) => void;
  onEditGame: (gameId: number) => void;
}

const TASK_LABELS: Record<string, string> = {
  REFEREE: "REF",
  SCORER: "SCORER",
  TIMER: "TIMER",
  SECOND_24_OPERATOR: "24 SEC",
};

export function GameCard({
  id,
  homeTeam,
  awayTeam,
  date,
  time,
  half,
  onSelectTask,
  onEditGame,
}: Props) {
  const { data: tasks = [], isLoading } = useQuery({
    queryKey: ["tasks-with-assignments", id],
    queryFn: () => getTasksWithAssignments(id),
  });

  // Check if all tasks are assigned
  const allAssigned =
    tasks.length > 0 && tasks.every((t) => t.assignments.length > 0);

  const handleSelectTask = useCallback(
    (task: TaskWithAssignments) => {
      onSelectTask(task, id);
    },
    [onSelectTask, id]
  );

  const dateObj = new Date(`${date}T${time}`);
  const formattedTime = dateObj.toLocaleTimeString("nl-BE", {
    hour: "2-digit",
    minute: "2-digit",
  });

  // Extract age category from team
  const ageBadge = homeTeam.age_category || "MIXED";

  if (isLoading) return <p>Loading tasks...</p>;

  return (
    <div className="game-card">
      <div className="game-card-header">
        <div className="game-card-left">
          <div className="game-badges">
            <span className="age-badge">{ageBadge}</span>
            {half && <span className="half-badge">H{half}</span>}
          </div>
          <div className="game-teams">
            <span className="home">{homeTeam.name}</span>
            <span className="vs">vs.</span>
            <span className="away">{awayTeam}</span>
          </div>
          <div className="game-meta">
            <span>{formattedTime}</span>
            <span>·</span>
            <span>Home Gym</span>
          </div>
        </div>
        <div className="game-card-right">
          {allAssigned && (
            <span className="staffed-badge">FULLY STAFFED</span>
          )}
          <button
            className="game-edit-btn"
            onClick={() => onEditGame(id)}
            title="Edit game"
          >
            ✎
          </button>
        </div>
      </div>

      <div className="task-chips">
        {tasks.map((task) => {
          const assigned = task.assignments;
          const label = TASK_LABELS[task.task_type] ?? task.task_type;
          const displayLabel = task.slot_number > 1 ? `${label} #${task.slot_number}` : label;

          // X10/X14 games only need 1 referee — extra ref slots are optional
          const isOptionalRef =
            task.task_type === "REFEREE" &&
            task.slot_number > 1 &&
            homeTeam.age_category &&
            ["X10", "X14"].includes(homeTeam.age_category);

          return (
            <div
              key={task.id}
              className={`task-chip ${
                assigned.length === 0
                  ? isOptionalRef
                    ? "optional"
                    : "unfilled"
                  : "filled"
              }`}
              onClick={() => handleSelectTask(task)}
            >
              <span className="chip-label">{displayLabel}</span>
              {assigned.length > 0 ? (
                <span className="chip-player">
                  {assigned[0]?.player?.full_name}
                  {assigned.length > 1 && <span className="chip-more"> +{assigned.length - 1}</span>}
                </span>
              ) : (
                <span className="chip-empty">Click to assign</span>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}
