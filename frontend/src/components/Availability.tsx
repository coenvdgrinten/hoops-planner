import { useQuery } from "@tanstack/react-query";
import { getAvailability } from "../api";
import type { AvailabilityDay, Season } from "../types";
import styles from "./Availability.module.css";

interface Props {
  season: Season;
}

export function Availability({ season }: Props) {
  const { data: days = [], isLoading, error } = useQuery({
    queryKey: ["availability", season.id],
    queryFn: () => getAvailability(season.id),
  });

  if (isLoading) return <p>Loading availability...</p>;
  if (error) return <p className="error">Error: {error.message}</p>;

  if (days.length === 0) {
    return (
      <div className={styles.availability}>
        <div className={styles["availability-header"]}>
          <h2>Availability</h2>
          <p className={styles["availability-subtitle"]}>
            Days where a team has an away game — its members and coaches are
            unavailable for tasks.
          </p>
        </div>
        <p className={styles["empty-msg"]}>
          No away games scheduled for this season.
        </p>
      </div>
    );
  }

  return (
    <div className={styles.availability}>
      <div className={styles["availability-header"]}>
        <h2>Availability</h2>
        <p className={styles["availability-subtitle"]}>
          Days where a team has an away game — its members and coaches are
          unavailable for tasks.
        </p>
      </div>
      {days.map((day: AvailabilityDay) => {
        const dateObj = new Date(`${day.date || "1970-01-01"}T00:00`);
        const formattedDate = dateObj.toLocaleDateString("nl-BE", {
          weekday: "long",
          day: "numeric",
          month: "short",
        });
        return (
          <div key={day.date} className={styles["availability-day"]}>
            <div className={styles["availability-date-label"]}>{formattedDate}</div>
            {day.away_games.map((game) => (
              <div key={game.game_id} className={styles["availability-game"]}>
                <div className={styles["availability-game-header"]}>
                  <span className={styles["availability-team"]}>
                    {game.team.name}
                  </span>
                  <span className={styles["availability-away"]}>AWAY</span>
                  <span className={styles["availability-opponent"]}>
                    vs {game.opponent}
                  </span>
                  {game.time && (
                    <span className={styles["availability-time"]}>{game.time}</span>
                  )}
                  <span className={styles["availability-count"]}>
                    {game.member_count} unavailable
                  </span>
                </div>
                <div className={styles["availability-members"]}>
                  {game.members.map((m) => (
                    <span
                      key={m.id}
                      className={`${styles["availability-member"]} ${
                        m.is_coach ? styles.coach : ""
                      }`}
                      title={m.is_coach ? "Coach" : "Player"}
                    >
                      {m.name}
                      {m.is_coach && " (C)"}
                    </span>
                  ))}
                </div>
              </div>
            ))}
          </div>
        );
      })}
    </div>
  );
}
