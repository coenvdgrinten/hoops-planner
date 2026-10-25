import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { getSeasonVersions, downloadVersionArtifact } from "../api";
import { useToastContext } from "./ToastContext";
import styles from "./Planner.module.css";

interface Props {
  seasonId: number;
  seasonName: string;
}

export function VersionsPanel({ seasonId, seasonName }: Props) {
  const { addToast } = useToastContext();
  const [selectedVersion, setSelectedVersion] = useState<number | null>(null);

  // staleTime: 0 — the list carries a live-schedule freshness line, so it must
  // refetch every time the tab is (re-)entered; the global 10s staleTime would
  // let a recent fetch mask schedule changes made while the tab was closed.
  const {
    data: versionsData,
    isLoading,
    error,
  } = useQuery({
    queryKey: ["season-versions", seasonId],
    queryFn: () => getSeasonVersions(seasonId),
    staleTime: 0,
  });
  const versions = versionsData?.versions ?? [];

  const handleDownload = async (number: number, format: "pdf" | "csv") => {
    try {
      await downloadVersionArtifact(seasonId, seasonName, number, format);
    } catch (err) {
      addToast(err instanceof Error ? err.message : "Download failed", "error");
    }
  };

  return (
    <div className={styles["versions-panel"]} data-testid="versions-panel">
      {isLoading ? (
        <p>Loading versions…</p>
      ) : error ? (
        <p className="error" data-testid="versions-error">
          Couldn't load schedule versions — please try again.
        </p>
      ) : versions.length === 0 ? (
        <div className={styles["versions-empty"]} data-testid="versions-empty">
          No schedule versions saved for this season yet.
          <br />
          Use the "save a schedule version" checkbox in the export dialog
          when you distribute a PDF or CSV.
        </div>
      ) : (
        <>
          {versions[0] && (
            <p
              className={styles["versions-freshness"]}
              data-testid="versions-freshness"
            >
              {versionsData?.live_matches === true
                ? `Live schedule matches v${versions[0].number}.`
                : `Live schedule has changed since v${versions[0].number}.`}
            </p>
          )}
          <ul className={styles["versions-list"]}>
            {versions.map((v) => (
              <li key={v.number}>
                <button
                  data-testid={`version-row-${v.number}`}
                  className={`${styles["version-row"]} ${selectedVersion === v.number ? styles["version-row-selected"] : ""}`}
                  onClick={() => setSelectedVersion(v.number)}
                >
                  <span className={styles["version-number"]}>v{v.number}</span>
                  <span className={styles["version-meta"]}>
                    {new Date(v.created_at).toLocaleString("nl-BE", {
                      dateStyle: "medium",
                      timeStyle: "short",
                    })}
                    {v.note ? ` — ${v.note}` : ""}
                  </span>
                  <span className={styles["version-format"]}>{v.artifact_format.toUpperCase()}</span>
                </button>
              </li>
            ))}
          </ul>
          {selectedVersion !== null &&
            (() => {
              const v = versions.find((x) => x.number === selectedVersion);
              if (!v) return null;
              return (
                <div className={styles["version-detail"]} data-testid="version-detail">
                  <h3>Version v{v.number}</h3>
                  <dl className={styles["version-detail-grid"]}>
                    <dt>Saved</dt>
                    <dd>
                      {new Date(v.created_at).toLocaleString("nl-BE", {
                        dateStyle: "long",
                        timeStyle: "short",
                      })}
                    </dd>
                    <dt>Note</dt>
                    <dd>{v.note || "—"}</dd>
                    <dt>Format</dt>
                    <dd>{v.artifact_format.toUpperCase()}</dd>
                  </dl>
                  {v.has_artifact ? (
                    <button
                      data-testid={`version-download-${v.number}`}
                      className={styles["btn-export"]}
                      onClick={() => void handleDownload(v.number, v.artifact_format)}
                    >
                      Download {v.artifact_format.toUpperCase()}
                    </button>
                  ) : (
                    <p className={styles["version-no-artifact"]}>
                      This version predates document storage and has no file to download.
                    </p>
                  )}
                </div>
              );
            })()}
        </>
      )}
    </div>
  );
}
