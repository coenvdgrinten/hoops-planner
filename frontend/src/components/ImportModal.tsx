import { useEffect, useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { importSchedule, importMembers } from "../api";

interface Props {
  type: "schedule" | "members";
  onClose: () => void;
  onSuccess: () => void;
}

export function ImportModal({ type, onClose, onSuccess }: Props) {
  const [csvText, setCsvText] = useState("");
  const [seasonName, setSeasonName] = useState("");
  const [replace, setReplace] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const queryClient = useQueryClient();

  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [onClose]);

  const importMutation = useMutation({
    mutationFn: async () => {
      if (type === "schedule") {
        return importSchedule(seasonName, csvText, replace);
      }
      return importMembers(csvText);
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["seasons"] });
      queryClient.invalidateQueries({ queryKey: ["players"] });
      queryClient.invalidateQueries({ queryKey: ["games"] });
      onSuccess();
    },
    onError: (err) => {
      setError(err instanceof Error ? err.message : "Import failed");
    },
  });

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    importMutation.mutate();
  };

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div role="dialog" className="modal" onClick={(e) => e.stopPropagation()}>
        <h2>Import {type === "schedule" ? "Schedule" : "Members"}</h2>
        <form onSubmit={handleSubmit}>
          {type === "schedule" && (
            <>
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
              <div className="form-group form-checkbox">
                <label>
                  <input
                    type="checkbox"
                    checked={replace}
                    onChange={(e) => setReplace(e.target.checked)}
                  />
                  Replace all existing games (deletes assignments)
                </label>
              </div>
            </>
          )}
          <div className="form-group">
            <label>CSV content:</label>
            <textarea
              value={csvText}
              onChange={(e) => setCsvText(e.target.value)}
              rows={10}
              required
              placeholder={
                type === "schedule"
                  ? "date, time, court, home_team, away_team, half\n2025-10-01, 14:00, 1, Vido X14-1, BC Roeselare, 1"
                  : "first_name, last_name, team, is_coach, referee_certification, coached_teams\nJan, Janssens, Vido X14-1, False, NONE,"
              }
            />
          </div>
          {error && <p className="error">{error}</p>}
          <div className="modal-actions">
            <button type="button" onClick={onClose} disabled={importMutation.isPending}>
              Cancel
            </button>
            <button type="submit" disabled={importMutation.isPending || !csvText.trim()}>
              {importMutation.isPending ? "Importing..." : `Import ${type}`}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
