import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { getSeasonStats } from "../api";
import type { ExportOptions } from "../api";
import type { Season, Game } from "../types";

const OPEN_TASK_LABELS: Record<string, string> = {
  REFEREE: "Referee",
  SCORER: "Scorer",
  TIMER: "Timer",
  ["24_SECOND_OPERATOR"]: "24-sec Operator",
};

function groupGamesByDate(games: Game[]): [string, Game[]][] {
  const sorted = [...games].sort((a, b) =>
    `${a.date}T${a.time}`.localeCompare(`${b.date}T${b.time}`),
  );
  const byDate = new Map<string, Game[]>();
  for (const g of sorted) {
    byDate.set(g.date, [...(byDate.get(g.date) ?? []), g]);
  }
  return [...byDate.entries()];
}

interface Props {
  format: "pdf" | "csv";
  season: Season;
  games: Game[];
  exporting: boolean;
  onClose: () => void;
  onExport: (options: ExportOptions) => void;
}

export function ExportDialog({ format, season, games, exporting, onClose, onExport }: Props) {
  const [exportScope, setExportScope] = useState<"" | "1" | "2" | "custom">("");
  const [selectedGameIds, setSelectedGameIds] = useState<number[]>([]);
  const [fullSeasonStats, setFullSeasonStats] = useState(false);
  const [saveVersion, setSaveVersion] = useState(false);
  const [versionNote, setVersionNote] = useState("");

  const pickerGamesByDate = groupGamesByDate(games);
  const allPickerGameIds = pickerGamesByDate.flatMap(([, dayGames]) =>
    dayGames.map((g) => g.id),
  );
  const allSelected =
    allPickerGameIds.length > 0 && selectedGameIds.length === allPickerGameIds.length;

  // Scoped so the warning only counts open tasks in the exported subset.
  const { data: scopeStats } = useQuery({
    queryKey: ["season-stats", season.id, exportScope],
    queryFn: () =>
      getSeasonStats(
        season.id,
        exportScope === "1" || exportScope === "2" ? exportScope : undefined,
      ),
  });
  const openTasks = scopeStats?.open_task_slots ?? 0;

  const handleExport = () => {
    onExport({
      saveVersion,
      note: versionNote.trim(),
      half: exportScope === "1" || exportScope === "2" ? exportScope : undefined,
      gameIds: exportScope === "custom" ? selectedGameIds : undefined,
      fullSeasonStats: fullSeasonStats || undefined,
    });
  };

  return (
    <div
      className="modal-overlay"
      onClick={() => {
        if (!exporting) onClose();
      }}
    >
      <div role="dialog" className="modal" onClick={(e) => e.stopPropagation()}>
        <h2>{format === "pdf" ? "Export PDF" : "Export CSV"}</h2>
        <div className="form-group">
          <span className="section-label">Which games?</span>
          <div className="segmented-control" role="radiogroup" aria-label="Export scope">
            <label className="segment">
              <input
                type="radio"
                name="export-scope"
                data-testid="export-scope-full"
                checked={exportScope === ""}
                onChange={() => setExportScope("")}
              />
              Whole season
            </label>
            <label className="segment">
              <input
                type="radio"
                name="export-scope"
                data-testid="export-scope-first-half"
                checked={exportScope === "1"}
                onChange={() => setExportScope("1")}
              />
              First half
            </label>
            <label className="segment">
              <input
                type="radio"
                name="export-scope"
                data-testid="export-scope-second-half"
                checked={exportScope === "2"}
                onChange={() => setExportScope("2")}
              />
              Second half
            </label>
            <label className="segment">
              <input
                type="radio"
                name="export-scope"
                data-testid="export-scope-custom"
                checked={exportScope === "custom"}
                onChange={() => setExportScope("custom")}
              />
              Custom
            </label>
          </div>
        </div>
        {exportScope === "custom" && (
          <div className="form-group">
            <div className="game-picker-header">
              <label>Choose the games to include</label>
              <div className="game-picker-tools">
                <span className="selection-count">
                  {selectedGameIds.length} selected
                </span>
                <button
                  type="button"
                  className="link-btn"
                  onClick={() =>
                    setSelectedGameIds(allSelected ? [] : allPickerGameIds)
                  }
                >
                  {allSelected ? "Clear all" : "Select all"}
                </button>
              </div>
            </div>
            <div className="game-picker" data-testid="game-picker">
              {pickerGamesByDate.map(([dateStr, dayGames]) => (
                <div key={dateStr}>
                  <div className="game-picker-date">
                    <span aria-hidden="true">📅</span>
                    {new Date(dateStr).toLocaleDateString("nl-NL", {
                      weekday: "short",
                      day: "numeric",
                      month: "short",
                      year: "numeric",
                    })}
                  </div>
                  {dayGames.map((g) => (
                    <label key={g.id} className="game-picker-item">
                      <input
                        type="checkbox"
                        data-testid={`game-picker-${g.id}`}
                        checked={selectedGameIds.includes(g.id)}
                        onChange={(e) =>
                          setSelectedGameIds((prev) =>
                            e.target.checked
                              ? [...prev, g.id]
                              : prev.filter((id) => id !== g.id),
                          )
                        }
                      />
                      {g.time.slice(0, 5)} · vs {g.opponent}{" "}
                      ({g.half === "2" ? "H2" : "H1"})
                    </label>
                  ))}
                </div>
              ))}
            </div>
          </div>
        )}
        {format === "pdf" && openTasks > 0 && (
          <div className="export-warning" role="alert">
            <div className="export-warning-head">
              <span className="export-warning-icon" aria-hidden="true">
                ⚠
              </span>
              <strong>
                {openTasks} unplanned task{openTasks === 1 ? "" : "s"} in this
                scope:
              </strong>
            </div>
            <div className="export-warning-chips" data-testid="pdf-warning-list">
              {Object.entries(scopeStats?.open_by_task_type ?? {}).map(
                ([type, count]) => (
                  <span key={type} className="chip">
                    {count} × {OPEN_TASK_LABELS[type] ?? type}
                  </span>
                ),
              )}
            </div>
            <p className="export-warning-note">
              These will appear as empty slots in the exported PDF.
            </p>
          </div>
        )}
        {/* Only shown when scoped — whole-season scope already implies full-season stats. */}
        {format === "pdf" && exportScope !== "" && (
          <div className="form-group">
            <div className="form-checkbox">
              <label>
                <input
                  type="checkbox"
                  data-testid="full-season-stats-checkbox"
                  checked={fullSeasonStats}
                  onChange={(e) => setFullSeasonStats(e.target.checked)}
                />
                Statistics cover the full season
              </label>
            </div>
            <p className="field-helper">
              Summary totals use the whole season, not just the selected games.
            </p>
          </div>
        )}
        <div className="form-group form-checkbox">
          <label>
            <input
              type="checkbox"
              data-testid="save-version-checkbox"
              checked={saveVersion}
              onChange={(e) => setSaveVersion(e.target.checked)}
            />
            Save a schedule version (snapshot of the whole season)
          </label>
        </div>
        {saveVersion && (
          <div className="form-group">
            <label htmlFor="version-note">Note (optional)</label>
            <input
              id="version-note"
              data-testid="version-note-input"
              value={versionNote}
              onChange={(e) => setVersionNote(e.target.value)}
              placeholder="e.g. sent to team managers"
              maxLength={500}
            />
          </div>
        )}
        <div className="modal-actions export-dialog-actions">
          <button onClick={onClose} disabled={exporting}>
            Cancel
          </button>
          <button
            data-testid="pdf-warning-export-btn"
            onClick={handleExport}
            disabled={exporting || (exportScope === "custom" && selectedGameIds.length === 0)}
          >
            {exporting ? "Generating…" : openTasks > 0 ? "Export anyway" : "Export"}
          </button>
        </div>
      </div>
    </div>
  );
}
