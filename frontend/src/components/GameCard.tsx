import { useCallback } from "react";
import { useQuery } from "@tanstack/react-query";
import { getTasksWithAssignments } from "../api";
import type { TaskWithAssignments } from "../types";
import styles from "./GameCard.module.css";

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
    <div className={styles["game-card"]}>
      <div className={styles["game-card-header"]}>
        <div className={styles["game-card-left"]}>
          <div className={styles["game-badges"]}>
            <span data-testid="age-badge" className={styles["age-badge"]}>{ageBadge}</span>
            {half && <span className={styles["half-badge"]}>H{half}</span>}
          </div>
          <div className={styles["game-teams"]}>
            <span className="home">{homeTeam.name}</span>
            <span className="vs">vs. </span>
            <span className="away">{awayTeam}</span>
          </div>
          <div className={styles["game-meta"]}>
            <span>{formattedTime}</span>
            <span>·</span>
            <span>Home Gym</span>
          </div>
        </div>
        <div className={styles["game-card-right"]}>
          {allAssigned && (
            <span className={styles["staffed-badge"]}>FULLY STAFFED</span>
          )}
          <button
            className={styles["game-edit-btn"]}
            onClick={() => onEditGame(id)}
            title="Edit game"
          >
            ✎
          </button>
        </div>
      </div>

      <div className={styles["task-chips"]}>
        {tasks.map((task) => {
          const assigned = task.assignments;
          const label = TASK_LABELS[task.task_type] ?? task.task_type;
          const displayLabel = task.slot_number > 1 ? `${label} #${task.slot_number}` : label;

          // Optional referee slots (e.g. a 2nd ref for X10/X14) are greyed out
          const isOptionalRef =
            task.task_type === "REFEREE" && task.optional;

          return (
            <div
              data-testid={`task-chip-${task.id}`}
              key={task.id}
              className={`${styles["task-chip"]} ${
                assigned.length === 0
                  ? isOptionalRef
                    ? styles.optional
                    : styles.unfilled
                  : styles.filled
              }`}
              onClick={() => handleSelectTask(task)}
            >
              <span className={styles["chip-label"]}>{displayLabel}</span>
              {assigned.length > 0 ? (
                <span className={styles["chip-player"]}>
                  {assigned[0]?.player?.full_name}
                  {assigned.length > 1 && <span className={styles["chip-more"]}> +{assigned.length - 1}</span>}
                </span>
              ) : (
                <span className={styles["chip-empty"]}>Click to assign</span>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}
