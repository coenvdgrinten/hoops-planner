import { Fragment, useCallback, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import {
  getGames,
  getSeasonStats,
  exportSeasonCsv,
  exportSeasonPdf,
  exportSeasonIcs,
} from "../api";
import type { Season, Game } from "../types";
import type { TaskWithAssignments } from "../types";
import { GameCard } from "./GameCard";
import { GameEditModal } from "./GameEditModal";
import styles from "./Planner.module.css";

interface Props {
  season: Season;
  onSelectTask: (task: TaskWithAssignments, gameId: number) => void;
  selectedGameId?: number | null;
  selectedTaskId?: number | null;
}

const OPEN_TASK_LABELS: Record<string, string> = {
  REFEREE: "Referee",
  SCORER: "Scorer",
  TIMER: "Timer",
  ["24_SECOND_OPERATOR"]: "24-sec Operator",
};

export function Planner({ season, onSelectTask, selectedGameId, selectedTaskId }: Props) {
  const [editingGame, setEditingGame] = useState<number | null>(null);
  const [showCreateModal, setShowCreateModal] = useState(false);
  const [showPdfWarning, setShowPdfWarning] = useState(false);
  const [pdfExporting, setPdfExporting] = useState(false);

  const { data: allGames = [], isLoading, error } = useQuery({
    queryKey: ["games", season.id],
    queryFn: () => getGames(season.id),
  });

  const { data: stats } = useQuery({
    queryKey: ["season-stats", season.id],
    queryFn: () => getSeasonStats(season.id),
  });
  const openTasks = stats?.open_task_slots ?? 0;

  const doExportPdf = useCallback(async () => {
    setPdfExporting(true);
    try {
      await exportSeasonPdf(season.id, season.name);
    } finally {
      setPdfExporting(false);
    }
  }, [season]);

  const handleExportPdfClick = useCallback(() => {
    if (pdfExporting) return;
    if (openTasks > 0) {
      setShowPdfWarning(true);
    } else {
      void doExportPdf();
    }
  }, [openTasks, pdfExporting, doExportPdf]);

  // Away games have no tasks; they live in the Availability view instead.
  const games = allGames.filter((g) => g.game_type !== "AWAY");

  const editingGameData = editingGame !== null ? games.find((g) => g.id === editingGame) : null;

  const handleSelectTask = useCallback(
    (task: TaskWithAssignments, gameId: number) => {
      onSelectTask(task, gameId);
    },
    [onSelectTask]
  );

  const handleEditGame = useCallback((gameId: number) => {
    setEditingGame(gameId);
  }, []);

  const handleEditClose = useCallback(() => {
    setEditingGame(null);
  }, []);

  const handleCreateClose = useCallback(() => {
    setShowCreateModal(false);
  }, []);

  if (isLoading) return <p>Loading games...</p>;
  if (error) return <p className="error">Error: {error.message}</p>;
  const hasGames = games.length > 0;

  // Group games by half, then by date, then by time slot. Within a slot each
  // court maps to at most one game, so games sharing a time always land in the
  // same visual row regardless of how tall their cards are.
  interface TimeSlot {
    time: string;
    cells: Record<string, Game>;
  }
  const grouped: Record<string, Record<string, TimeSlot[]>> = {};
  const sorted = [...games].sort((a, b) => {
    const ha = a.half || "1";
    const hb = b.half || "1";
    if (ha !== hb) return ha.localeCompare(hb);
    const da = `${a.date}T${a.time}`;
    const db = `${b.date}T${b.time}`;
    return da.localeCompare(db);
  });
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
              ⚠ {stats.conflict_count}{" "}
              {stats.conflict_count === 1 ? "conflict" : "conflicts"} — assignments no longer valid
            </div>
          )}
        </div>
        <div className={styles["planner-actions"]}>
          <button
            data-testid="export-csv-btn"
            className={styles["btn-export"]}
            onClick={() => exportSeasonCsv(season.id, season.name)}
          >
            Export CSV
          </button>
          <button
            data-testid="export-pdf-btn"
            className={styles["btn-export"]}
            onClick={handleExportPdfClick}
            disabled={pdfExporting}
          >
            {pdfExporting ? "Generating…" : "Export PDF"}
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
      {hasGames ? (
        <div className={styles["games-by-date"]}>
        {Object.entries(grouped).map(([halfKey, dates]) => {
          const halfLabel = halfKey === "1" ? "First Half" : "Second Half";
          return (
            <div key={halfKey} className={styles["half-group"]}>
              <div className={styles["half-label"]}>{halfLabel}</div>
              {Object.entries(dates).map(([date, slots]) => {
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
      )}
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
      {showPdfWarning && (
        <div className="modal-overlay" onClick={() => setShowPdfWarning(false)}>
          <div role="dialog" className="modal" onClick={(e) => e.stopPropagation()}>
            <h2>Export PDF</h2>
            <p style={{ marginBottom: 8 }}>
              There are still {openTasks} unplanned task{openTasks === 1 ? "" : "s"} in this
              schedule:
            </p>
            <ul
              data-testid="pdf-warning-list"
              style={{
                margin: "0 0 16px 20px",
                fontSize: 13,
                color: "var(--color-text-secondary)",
              }}
            >
              {Object.entries(stats?.open_by_task_type ?? {}).map(([type, count]) => (
                <li key={type}>
                  {count} × {OPEN_TASK_LABELS[type] ?? type}
                </li>
              ))}
            </ul>
            <p style={{ fontSize: 13, color: "var(--color-text-muted)", marginBottom: 16 }}>
              These will appear as empty slots in the exported PDF.
            </p>
            <div className="modal-actions">
              <button onClick={() => setShowPdfWarning(false)}>Cancel</button>
              <button
                data-testid="pdf-warning-export-btn"
                onClick={() => {
                  setShowPdfWarning(false);
                  void doExportPdf();
                }}
              >
                Export anyway
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
