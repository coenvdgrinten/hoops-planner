import { TaskCard } from "./TaskCard";

interface Team {
  name: string;
}

interface Props {
  id: number;
  homeTeam: Team;
  awayTeam: string;
  date: string;
  time: string;
  court: string;
}

export function GameCard({ id, homeTeam, awayTeam, date, time, court }: Props) {
  const dateObj = new Date(`${date}T${time}`);
  const formattedDate = dateObj.toLocaleDateString("nl-BE", {
    weekday: "short",
    day: "numeric",
    month: "short",
  });
  const formattedTime = dateObj.toLocaleTimeString("nl-BE", {
    hour: "2-digit",
    minute: "2-digit",
  });

  return (
    <div className="game-card">
      <div className="game-header">
        <div className="game-teams">
          <span className="home">{homeTeam.name}</span>
          <span className="vs">vs</span>
          <span className="away">{awayTeam}</span>
        </div>
        <div className="game-meta">
          <span>{formattedDate}</span>
          <span>{formattedTime}</span>
          <span>Court {court}</span>
        </div>
      </div>
      <TaskCard gameId={id} />
    </div>
  );
}
