import { useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { getReservations, getGymCoverage, getGames, getSiteConfig } from "../api";
import type { Game, GymReservation, Season, SiteConfigData } from "../types";
import { AlertTriangleIcon, CalendarIcon, CheckIcon, PencilIcon, PlusIcon, TrashIcon } from "./Icons";
import { ReservationModal } from "./ReservationModal";
import styles from "./GymPanel.module.css";

interface Props {
  season: Season;
}

function toMinutes(t: string): number {
  const [h = 0, m = 0] = t.split(":").map(Number);
  return h * 60 + m;
}

function fmtMin(mins: number): string {
  const h = Math.floor(mins / 60) % 24;
  const m = mins % 60;
  return `${String(h).padStart(2, "0")}:${String(m).padStart(2, "0")}`;
}

function formatDuration(minutes: number): string {
  const h = Math.floor(minutes / 60);
  const m = minutes % 60;
  if (h === 0) return `${m}m`;
  if (m === 0) return `${h}h`;
  return `${h}h ${m}m`;
}

/** Required gym window for a game, in minutes since midnight. */
function gameWindow(game: Game, cfg: SiteConfigData): { start: number; end: number } {
  const t = toMinutes(game.time);
  return {
    start: t - cfg.gym_margin_before_minutes,
    end: t + cfg.gym_game_duration_minutes + cfg.gym_margin_after_minutes,
  };
}

type DaySegKind = "covered" | "surplus" | "needed" | "empty";

interface DaySegment {
  from: number;
  to: number;
  kind: DaySegKind;
  /** Games whose required window overlaps this slice (for labels/tooltips). */
  games: Game[];
}

/**
 * Build ONE unified timeline for a match day by sweeping across every interval
 * boundary (reservation edges + game-window edges) and classifying each slice:
 *
 *   covered = reserved AND used by a game
 *   surplus = reserved but unused (returnable)
 *   needed  = a game needs it but it is NOT reserved (action required)
 *   empty   = neither reserved nor needed
 *
 * The bar therefore spans the union of all reservations and game windows for
 * the day, so a single glance shows what is booked, what is free, and what is
 * still missing.
 */
function buildDayTimeline(
  reservations: GymReservation[],
  games: Game[],
  cfg: SiteConfigData,
): DaySegment[] {
  const resIntervals = reservations.map((r) => ({
    start: toMinutes(r.start_time),
    end: toMinutes(r.end_time),
  }));
  const gameIntervals = games
    .filter((g) => g.time)
    .map((g) => ({ game: g, ...gameWindow(g, cfg) }));

  const bounds = new Set<number>();
  for (const r of resIntervals) {
    bounds.add(r.start);
    bounds.add(r.end);
  }
  for (const g of gameIntervals) {
    bounds.add(g.start);
    bounds.add(g.end);
  }
  if (bounds.size < 2) return [];
  const sorted = [...bounds].sort((a, b) => a - b);

  const segments: DaySegment[] = [];
  for (let i = 0; i < sorted.length - 1; i++) {
    const from = sorted[i]!;
    const to = sorted[i + 1]!;
    if (to <= from) continue;
    const mid = (from + to) / 2;
    const inRes = resIntervals.some((r) => r.start <= mid && mid < r.end);
    const overlapping = gameIntervals
      .filter((g) => g.start <= mid && mid < g.end)
      .map((g) => g.game);
    let kind: DaySegKind;
    if (inRes && overlapping.length > 0) kind = "covered";
    else if (inRes) kind = "surplus";
    else if (overlapping.length > 0) kind = "needed";
    else kind = "empty";
    segments.push({ from, to, kind, games: overlapping });
  }
  return segments;
}

export function GymPanel({ season }: Props) {
  const [modalState, setModalState] = useState<
    { reservation?: GymReservation; date?: string } | null
  >(null);

  const { data: reservations = [], isLoading } = useQuery({
    queryKey: ["reservations", season.id],
    queryFn: () => getReservations(season.id),
  });

  const { data: coverage } = useQuery({
    queryKey: ["gym-coverage", season.id],
    queryFn: () => getGymCoverage(season.id),
  });

  const { data: allGames = [] } = useQuery({
    queryKey: ["games", season.id],
    queryFn: () => getGames(season.id),
  });

  const { data: siteConfig } = useQuery({
    queryKey: ["site-config"],
    queryFn: getSiteConfig,
  });

  const homeGames = useMemo(
    () => allGames.filter((g) => g.game_type !== "AWAY"),
    [allGames],
  );

  const groups = useMemo(() => {
    if (!siteConfig) return [];
    const dates = new Set<string>();
    for (const r of reservations) dates.add(r.date);
    for (const g of coverage?.uncovered_games ?? []) dates.add(g.date);

    return [...dates].sort().map((date) => {
      const dayReservations = reservations.filter((r) => r.date === date);
      const dayUncovered = (coverage?.uncovered_games ?? []).filter((g) => g.date === date);
      const dayGames = homeGames.filter((g) => g.date === date);
      const segments = buildDayTimeline(dayReservations, dayGames, siteConfig);

      const totalReservedMin = dayReservations.reduce(
        (sum, r) => sum + (toMinutes(r.end_time) - toMinutes(r.start_time)),
        0,
      );
      const daySurplusMin = (coverage?.surplus ?? [])
        .filter((s) => s.date === date)
        .reduce((sum, s) => sum + s.minutes, 0);

      return { date, dayReservations, dayUncovered, segments, totalReservedMin, daySurplusMin };
    });
  }, [reservations, coverage, homeGames, siteConfig]);

  if (isLoading) return <p>Loading reservations...</p>;

  const totalSurplusMin = (coverage?.surplus ?? []).reduce((s, x) => s + x.minutes, 0);

  const handleModalClose = () => setModalState(null);

  return (
    <div className={styles["gym-panel"]}>
      <div className={styles["gym-header"]}>
        <div>
          <h2 className={styles["gym-title"]}>Gym Reservations</h2>
          {coverage && (
            <p className={styles["gym-subtitle"]}>
              {coverage.covered_games} of {coverage.total_home_games} home games covered
              {totalSurplusMin > 0 && ` · ${formatDuration(totalSurplusMin)} returnable`}
            </p>
          )}
        </div>
        <button className={styles["btn-add"]} onClick={() => setModalState({})}>
          + Add Reservation
        </button>
      </div>

      {groups.length === 0 ? (
        <p className={styles["empty-msg"]}>
          No reservations yet. Click "+ Add Reservation" to book the gym.
        </p>
      ) : (
        groups.map((group) => {
          const dateObj = new Date(`${group.date}T00:00`);
          const formattedDate = dateObj.toLocaleDateString("nl-BE", {
            weekday: "long",
            day: "numeric",
            month: "long",
          });
          return (
            <div key={group.date} className={styles["date-group"]}>
              <div className={styles["date-header"]}>
                <span className={styles["date-label"]}>
                  <CalendarIcon size={16} />
                  {formattedDate}
                </span>
                {group.dayUncovered.length > 0 ? (
                  <span className={`${styles.badge} ${styles["badge-danger"]}`}>
                    {group.dayUncovered.length}{" "}
                    {group.dayUncovered.length === 1 ? "game" : "games"} uncovered
                  </span>
                ) : group.dayReservations.length > 0 ? (
                  <span className={styles.badge}>
                    {group.dayReservations.length}{" "}
                    {group.dayReservations.length === 1 ? "slot" : "slots"} ·{" "}
                    {formatDuration(group.totalReservedMin)} reserved
                  </span>
                ) : null}
              </div>

              {/* Reservation management pills (one row above the bar) */}
              {group.dayReservations.length > 0 && (
                <div className={styles["res-pills"]}>
                  {group.dayReservations.map((res) => (
                    <div key={res.id} className={styles["res-pill"]}>
                      <span className={styles["res-pill-time"]}>
                        {res.start_time.slice(0, 5)}–{res.end_time.slice(0, 5)}
                      </span>
                      {res.note && <span className={styles["res-pill-note"]}>{res.note}</span>}
                      <span className={styles["res-pill-actions"]}>
                        <button
                          className={styles["icon-btn-sm"]}
                          title="Edit reservation"
                          onClick={() => setModalState({ reservation: res })}
                        >
                          <PencilIcon size={13} />
                        </button>
                        <button
                          className={`${styles["icon-btn-sm"]} ${styles.danger}`}
                          title="Delete reservation"
                          onClick={() => setModalState({ reservation: res })}
                        >
                          <TrashIcon size={13} />
                        </button>
                      </span>
                    </div>
                  ))}
                </div>
              )}

              {/* Unified day timeline */}
              {group.segments.length > 0 && (() => {
                const rangeStart = group.segments[0]!.from;
                const rangeEnd = group.segments[group.segments.length - 1]!.to;
                const rangeTotal = Math.max(1, rangeEnd - rangeStart);

                // Ticks at every boundary.
                const ticks: { pos: number; label: string }[] = [
                  { pos: 0, label: fmtMin(rangeStart) },
                  ...group.segments.slice(1).map((s) => ({
                    pos: ((s.from - rangeStart) / rangeTotal) * 100,
                    label: fmtMin(s.from),
                  })),
                  { pos: 100, label: fmtMin(rangeEnd) },
                ];

                // Label each game once, at its leftmost slice.
                const labeled = new Set<number>();

                return (
                  <div className={styles.timeline}>
                    <div className={styles["timeline-bar"]}>
                      {group.segments.map((seg, i) => {
                        const pct = ((seg.to - seg.from) / rangeTotal) * 100;
                        const cls =
                          seg.kind === "covered"
                            ? styles["seg-covered"]
                            : seg.kind === "surplus"
                              ? styles["seg-surplus"]
                              : seg.kind === "needed"
                                ? styles["seg-needed"]
                                : styles["seg-empty"];

                        const fresh = seg.games.find((g) => !labeled.has(g.id));
                        let label = "";
                        let title = `${fmtMin(seg.from)}–${fmtMin(seg.to)}`;
                        if (seg.kind === "covered" || seg.kind === "needed") {
                          title = seg.games
                            .map((g) => `${g.own_team.name} ${g.time} vs ${g.opponent}`)
                            .join("\n");
                          if (fresh) {
                            label = `${fresh.own_team.name.replace(/^Vido\s*/, "")} ${fresh.time.slice(0, 5)}`;
                            if (pct > 8) labeled.add(fresh.id);
                          }
                        } else if (seg.kind === "surplus") {
                          label = "SURPLUS";
                          title = `Returnable: ${fmtMin(seg.from)}–${fmtMin(seg.to)}`;
                        } else {
                          title = `Free: ${fmtMin(seg.from)}–${fmtMin(seg.to)}`;
                        }

                        return (
                          <div
                            key={i}
                            className={`${styles.seg} ${cls}`}
                            style={{ width: `${pct}%` }}
                            title={title}
                          >
                            {pct > 8 && label && (
                              <span
                                className={`${styles["seg-label"]} ${
                                  seg.kind === "surplus"
                                    ? styles["seg-label--surplus"]
                                    : seg.kind === "needed"
                                      ? styles["seg-label--needed"]
                                      : ""
                                }`}
                              >
                                {label}
                              </span>
                            )}
                          </div>
                        );
                      })}
                    </div>

                    {/* Tick marks at every boundary */}
                    <div className={styles["timeline-ticks"]}>
                      {ticks.map((t, i) => (
                        <span
                          key={i}
                          className={`${styles.tick} ${i === 0 ? styles["tick--first"] : ""} ${i === ticks.length - 1 ? styles["tick--last"] : ""}`}
                          style={{ left: `${t.pos}%`, transform: i === 0 ? "none" : i === ticks.length - 1 ? "translateX(-100%)" : "translateX(-50%)" }}
                        >
                          {t.label}
                        </span>
                      ))}
                    </div>

                    {/* Summary line */}
                    <div className={styles["day-summary"]}>
                      {group.dayUncovered.length > 0 ? (
                        <span className={styles["summary-needed"]}>
                          <AlertTriangleIcon size={12} />
                          {group.dayUncovered.length}{" "}
                          {group.dayUncovered.length === 1 ? "game needs" : "games need"} a reservation
                        </span>
                      ) : (
                        <span className={styles["summary-ok"]}>
                          <CheckIcon size={12} /> Fully covered
                        </span>
                      )}
                      {group.daySurplusMin > 0 && (
                        <span className={styles["summary-surplus"]}>
                          {formatDuration(group.daySurplusMin)} returnable
                        </span>
                      )}
                    </div>
                  </div>
                );
              })()}

              {/* Quick add for dates that still need coverage */}
              {group.dayUncovered.length > 0 && (
                <button
                  className={styles["add-for-date"]}
                  onClick={() => setModalState({ date: group.date })}
                >
                  <PlusIcon size={14} /> Add reservation for this date
                </button>
              )}
            </div>
          );
        })
      )}

      {modalState && (
        <ReservationModal
          reservation={modalState.reservation}
          seasonId={season.id}
          defaultDate={modalState.date}
          onClose={handleModalClose}
          onSuccess={handleModalClose}
        />
      )}
    </div>
  );
}
