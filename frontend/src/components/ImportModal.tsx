import { useEffect, useState } from "react";
import { importSchedule, importMembers } from "../api";

interface Props {
  type: "schedule" | "members";
  onClose: () => void;
  onSuccess: () => void;
}

export function ImportModal({ type, onClose, onSuccess }: Props) {
  const [csvText, setCsvText] = useState("");
  const [seasonName, setSeasonName] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [onClose]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setError(null);

    try {
      if (type === "schedule") {
        await importSchedule(seasonName, csvText);
      } else {
        await importMembers(csvText);
      }
      onSuccess();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Import failed");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div role="dialog" className="modal" onClick={(e) => e.stopPropagation()}>
        <h2>Import {type === "schedule" ? "Schedule" : "Members"}</h2>
        {type === "schedule" && (
          <div className="form-group">
            <label>Season name:</label>
            <input
              type="text"
              value={seasonName}
              onChange={(e) => setSeasonName(e.target.value)}
              placeholder="e.g. 2025-2026"
              required
            />
          </div>
        )}
        <form onSubmit={handleSubmit}>
          <div className="form-group">
            <label>CSV content:</label>
            <textarea
              value={csvText}
              onChange={(e) => setCsvText(e.target.value)}
              rows={10}
              required
              placeholder={
                type === "schedule"
                  ? "date, time, court, home_team, away_team\n2025-10-01, 14:00, 1, Vido X14-1, BC Roeselare"
                  : "first_name, last_name, team, is_coach, referee_certification\nJan, Janssens, Vido X14-1, False, T1"
              }
            />
          </div>
          {error && <p className="error">{error}</p>}
          <div className="modal-actions">
            <button type="button" onClick={onClose} disabled={loading}>
              Cancel
            </button>
            <button type="submit" disabled={loading || !csvText.trim()}>
              {loading ? "Importing..." : `Import ${type}`}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
