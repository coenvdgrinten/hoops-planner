import { Fragment, useCallback, useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import {
  getGames,
  getSeasonStats,
  getGymCoverage,
  getReplacementTasks,
  exportSeasonCsv,
  exportSeasonPdf,
  exportSeasonIcs,
} from "../api";
import type { ExportOptions, ExportResult } from "../api";
import { useToastContext } from "./ToastContext";
import type { Season, Game, Task, TaskWithAssignments } from "../types";
import { GameCard } from "./GameCard";
import { GameEditModal } from "./GameEditModal";
import { ExportDialog } from "./ExportDialog";
import { VersionsPanel } from "./VersionsPanel";
import { GymPanel } from "./GymPanel";
import { AlertTriangleIcon } from "./Icons";
import styles from "./Planner.module.css";

interface Props {
  season: Season;
  onSelectTask: (task: TaskWithAssignments, gameId: number) => void;
  selectedGameId?: number | null;
  selectedTaskId?: number | null;
}

interface TimeSlot {
  time: string;
  cells: Record<string, Game>;
}

type GroupedSchedule = Record<string, Record<string, TimeSlot[]>>;

/** Group games by half → date → time slot, with each court as a cell. */
function groupGamesBySchedule(games: Game[]): GroupedSchedule {
  const sorted = [...games].sort((a, b) => {
    const ha = a.half || "1";
    const hb = b.half || "1";
    if (ha !== hb) return ha.localeCompare(hb);
    return `${a.date}T${a.time}`.localeCompare(`${b.date}T${b.time}`);
  });
  const grouped: GroupedSchedule = {};
  for (const game of sorted) {
    const h = game.half || "1";
    const d = game.date || "";
    const t = game.time || "";
    const c = game.court || "1";
    if (!grouped[h]) grouped[h] = {};
    if (!grouped[h][d]) grouped[h][d] = [];
    const slots = grouped[h][d];
    let slot = slots.find((s) => s.time === t);
    if (!slot) {
      slot = { time: t, cells: {} };
      slots.push(slot);
    }
    slot.cells[c] = game;
  }
  return grouped;
}

export function Planner({ season, onSelectTask, selectedGameId, selectedTaskId }: Props) {
  const { addToast } = useToastContext();
  const queryClient = useQueryClient();
  const [editingGame, setEditingGame] = useState<number | null>(null);
  const [showCreateModal, setShowCreateModal] = useState(false);
  const [exportFormat, setExportFormat] = useState<"pdf" | "csv" | null>(null);
  const [exporting, setExporting] = useState(false);
  const [tab, setTab] = useState<
    "schedule" | "replacements" | "versions" | "gym"
  >("schedule");

  const { data: allGames = [], isLoading, error } = useQuery({
    queryKey: ["games", season.id],
    queryFn: () => getGames(season.id),
  });

  const { data: stats } = useQuery({
    queryKey: ["season-stats", season.id],
    queryFn: () => getSeasonStats(season.id),
  });

  const { data: gymCoverage } = useQuery({
    queryKey: ["gym-coverage", season.id],
    queryFn: () => getGymCoverage(season.id),
  });

  const {
    data: replacementTasks = [],
    isLoading: replacementsLoading,
    error: replacementsError,
  } = useQuery({
    queryKey: ["replacement-tasks", season.id],
    queryFn: () => getReplacementTasks(season.id),
  });

  const doExport = useCallback(
    async (options: ExportOptions) => {
      const format = exportFormat!;
      setExporting(true);
      try {
        const result: ExportResult =
          format === "pdf"
            ? await exportSeasonPdf(season.id, season.name, options)
            : await exportSeasonCsv(season.id, season.name, options);
        if (options.saveVersion && result.versionMessage) {
          addToast(result.versionMessage, result.versionNumber ? "success" : "info");
          queryClient.invalidateQueries({ queryKey: ["season-versions", season.id] });
        }
        setExportFormat(null);
      } catch (err) {
        addToast(err instanceof Error ? err.message : "Export failed", "error");
      } finally {
        setExporting(false);
      }
    },
    [addToast, queryClient, exportFormat, season],
  );

  // Away games are hidden from the planner grid; they surface in the
  // Availability view instead.
  const games = allGames.filter((g) => g.game_type !== "AWAY");

  const handleSelectTask = useCallback(
    (task: TaskWithAssignments, gameId: number) => {
      onSelectTask(task, gameId);
    },
    [onSelectTask]
  );

  const handleEditGame = useCallback((gameId: number) => {
    setEditingGame(gameId);
  }, []);

  const handleOpenReplacementTask = useCallback(
    (task: Task) => {
      setTab("schedule");
      onSelectTask(
        {
          ...task,
          game: task.game.id,
          assignments: [],
        },
        task.game.id,
      );
      requestAnimationFrame(() => {
        document
          .getElementById(`game-card-${task.game.id}`)
          ?.scrollIntoView({ behavior: "smooth", block: "center" });
      });
    },
    [onSelectTask],
  );

  const handleEditClose = useCallback(() => {
    setEditingGame(null);
  }, []);

  const handleCreateClose = useCallback(() => {
    setShowCreateModal(false);
  }, []);

  if (isLoading) return <p>Loading games...</p>;
  if (error) return <p className="error">Error: {error.message}</p>;
  const hasGames = games.length > 0;
  const grouped = groupGamesBySchedule(games);
  const editingGameData = editingGame !== null ? games.find((g) => g.id === editingGame) : null;

  return (
    <div className={styles.planner}>
      <div className={styles["planner-header"]}>
        <div>
          <h2>Game Schedule</h2>
          <p className={styles["planner-subtitle"]}>
            Assign members to standard tasks like refereeing, scoring, and timing.
          </p>
          {stats && (
            <div className={styles["fill-bar"]} data-testid="fill-rate-bar">
              <div className={styles["fill-bar-track"]}>
                <div
                  className={styles["fill-bar-inner"]}
                  style={{ width: `${Math.min(100, stats.fill_rate)}%` }}
                />
              </div>
              <span className={styles["fill-bar-label"]}>
                {Math.round(stats.fill_rate)}% filled
              </span>
            </div>
          )}
          {stats && (stats.conflict_count ?? 0) > 0 && (
            <div className={styles["conflict-badge"]} data-testid="conflict-count">
              <AlertTriangleIcon size={13} /> {stats.conflict_count}{" "}
              {stats.conflict_count === 1 ? "conflict" : "conflicts"} — assignments no longer valid
            </div>
          )}
          {gymCoverage && gymCoverage.uncovered_games.length > 0 && (
            <button
              className={styles["conflict-badge"]}
              data-testid="gym-coverage-badge"
              onClick={() => setTab("gym")}
              title="View uncovered games in the Gym tab"
            >
              <AlertTriangleIcon size={13} /> {gymCoverage.uncovered_games.length}{" "}
              {gymCoverage.uncovered_games.length === 1 ? "game" : "games"} without a gym
              reservation
            </button>
          )}
        </div>
        <div className={styles["planner-actions"]}>
          <button
            data-testid="export-csv-btn"
            className={styles["btn-export"]}
            onClick={() => setExportFormat("csv")}
            disabled={exporting}
          >
            Export CSV
          </button>
          <button
            data-testid="export-pdf-btn"
            className={styles["btn-export"]}
            onClick={() => setExportFormat("pdf")}
            disabled={exporting}
          >
            {exporting ? "Generating…" : "Export PDF"}
          </button>
          <button
            data-testid="export-ics-btn"
            className={styles["btn-export"]}
            onClick={() => exportSeasonIcs(season.id, season.name)}
          >
            Calendar
          </button>
          <button className={styles["btn-add-game"]} onClick={() => setShowCreateModal(true)}>
            + Add Game
          </button>
        </div>
      </div>
      <div className={styles["planner-tabs"]} role="tablist">
        <button
          role="tab"
          aria-selected={tab === "schedule"}
          data-testid="planner-tab-schedule"
          className={`${styles["planner-tab"]} ${tab === "schedule" ? styles["planner-tab-active"] : ""}`}
          onClick={() => setTab("schedule")}
        >
          Schedule
        </button>
        <button
          role="tab"
          aria-selected={tab === "replacements"}
          data-testid="planner-tab-replacements"
          className={`${styles["planner-tab"]} ${tab === "replacements" ? styles["planner-tab-active"] : ""}`}
          onClick={() => setTab("replacements")}
        >
          Needs replacement{replacementTasks.length > 0 ? ` (${replacementTasks.length})` : ""}
        </button>
        <button
          role="tab"
          aria-selected={tab === "versions"}
          data-testid="planner-tab-versions"
          className={`${styles["planner-tab"]} ${tab === "versions" ? styles["planner-tab-active"] : ""}`}
          onClick={() => setTab("versions")}
        >
          Versions
        </button>
        <button
          role="tab"
          aria-selected={tab === "gym"}
          data-testid="planner-tab-gym"
          className={`${styles["planner-tab"]} ${tab === "gym" ? styles["planner-tab-active"] : ""}`}
          onClick={() => setTab("gym")}
        >
          Gym
        </button>
      </div>
      {tab === "schedule" && (hasGames ? (
        <div className={styles["games-by-date"]}>
        {Object.entries(grouped).map(([halfKey, dates]) => {
          const halfLabel = halfKey === "1" ? "First Half" : "Second Half";
          return (
            <div key={halfKey} className={styles["half-group"]}>
              <div className={styles["half-label"]}>{halfLabel}</div>
              {Object.entries(dates).map(([date, slots]) => {
                // The 1970-01-01 sentinel sorts before any real date, so
                // undated games render first.
                const dateObj = new Date(`${date || "1970-01-01"}T00:00`);
                const formattedDate = dateObj.toLocaleDateString("nl-BE", {
                  weekday: "long",
                  day: "numeric",
                  month: "short",
                });
                const today = new Date();
                today.setHours(0, 0, 0, 0);
                const isFuture = dateObj >= today;
                const courts = Array.from(
                  new Set(slots.flatMap((s) => Object.keys(s.cells)))
                ).sort((a, b) => Number(a) - Number(b));
                const sortedSlots = [...slots].sort((a, b) => a.time.localeCompare(b.time));
                return (
                  <div key={date} className={styles["date-group"]}>
                    <div data-testid="date-label" className={styles["date-label"]}>
                      {isFuture && <span className={styles["upcoming-badge"]}>Upcoming Games</span>}
                      <span>{formattedDate}</span>
                    </div>
                    <div
                      className={styles["schedule-grid"]}
                      style={{ gridTemplateColumns: `repeat(${courts.length}, minmax(0, 1fr))` }}
                    >
                      {courts.map((court) => (
                        <div key={`header-${court}`} className={styles["court-header"]}>
                          Court {court}
                        </div>
                      ))}
                      {sortedSlots.map((slot) => (
                        <Fragment key={slot.time}>
                          {courts.map((court) => {
                            const game = slot.cells[court];
                            return (
                              <div key={`${slot.time}-${court}`} className={styles["grid-cell"]}>
                                {game && (
                                  <GameCard
                                    id={game.id}
                                    isSelected={game.id === selectedGameId}
                                    ownTeam={game.own_team}
                                    opponent={game.opponent}
                                    date={game.date}
                                    time={game.time}
                                    court={game.court}
                                    location={game.location}
                                    half={game.half}
                                    isSelectedTaskId={selectedTaskId}
                                    onSelectTask={handleSelectTask}
                                    onEditGame={handleEditGame}
                                  />
                                )}
                              </div>
                            );
                          })}
                        </Fragment>
                      ))}
                    </div>
                  </div>
                );
              })}
            </div>
          );
        })}
        </div>
      ) : (
        <p>No games in this season yet. Click "+ Add Game" to create one.</p>
      ))}
      {tab === "replacements" && (
        <section className={styles["replacement-overview"]} data-testid="replacement-overview">
          <div>
            <h3>Tasks needing a replacement</h3>
            <p>These tasks were reported as needing a new assignee.</p>
          </div>
          {replacementsLoading ? (
            <p>Loading replacement requests...</p>
          ) : replacementsError ? (
            <p className="error">Error: {replacementsError.message}</p>
          ) : replacementTasks.length === 0 ? (
            <p className={styles["replacement-empty"]}>No tasks currently need a replacement.</p>
          ) : (
            <ul className={styles["replacement-list"]}>
              {replacementTasks.map((task) => {
                const date = new Date(`${task.game.date}T${task.game.time}`);
                const formattedDate = date.toLocaleDateString("nl-BE", {
                  weekday: "short",
                  day: "numeric",
                  month: "short",
                });
                const formattedTime = date.toLocaleTimeString("nl-BE", {
                  hour: "2-digit",
                  minute: "2-digit",
                });
                const taskLabel =
                  task.task_type === "24_SECOND_OPERATOR"
                    ? "24-second operator"
                    : task.task_type.toLowerCase();
                return (
                  <li key={task.id}>
                    <button
                      className={styles["replacement-row"]}
                      data-testid={`replacement-task-${task.id}`}
                      onClick={() => handleOpenReplacementTask(task)}
                    >
                      <span className={styles["replacement-row-game"]}>
                        {task.game.own_team.name} vs. {task.game.opponent}
                      </span>
                      <span className={styles["replacement-row-meta"]}>
                        {formattedDate} · {formattedTime} · Court {task.game.court}
                      </span>
                      <span className={styles["replacement-row-task"]}>
                        {taskLabel}{task.slot_number > 1 ? ` #${task.slot_number}` : ""}
                      </span>
                    </button>
                  </li>
                );
              })}
            </ul>
          )}
        </section>
      )}
      {tab === "versions" && <VersionsPanel seasonId={season.id} seasonName={season.name} />}
      {tab === "gym" && <GymPanel season={season} />}
      {editingGameData && (
        <GameEditModal
          game={editingGameData}
          seasonId={season.id}
          onClose={handleEditClose}
          onSuccess={handleEditClose}
        />
      )}
      {showCreateModal && (
        <GameEditModal
          seasonId={season.id}
          onClose={handleCreateClose}
          onSuccess={handleCreateClose}
        />
      )}
      {exportFormat && (
        <ExportDialog
          format={exportFormat}
          season={season}
          games={games}
          exporting={exporting}
          onClose={() => setExportFormat(null)}
          onExport={(opts) => void doExport(opts)}
        />
      )}
    </div>
  );
}
