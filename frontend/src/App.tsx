import { useState } from "react";
import { SeasonSelector } from "./components/SeasonSelector";
import { Planner } from "./components/Planner";
import { Statistics } from "./components/Statistics";
import { MemberView } from "./components/MemberView";
import { ImportModal } from "./components/ImportModal";
import type { Season } from "./types";
import "./App.css";

type View = "planner" | "statistics" | "members";

export function App() {
  const [selectedSeason, setSelectedSeason] = useState<Season | null>(null);
  const [importType, setImportType] = useState<"schedule" | "members" | null>(null);
  const [currentView, setCurrentView] = useState<View>("planner");

  return (
    <div className="app">
      <header>
        <h1>Hoops Planner</h1>
        <nav>
          <button onClick={() => setImportType("schedule")}>Import Schedule</button>
          <button onClick={() => setImportType("members")}>Import Members</button>
          <SeasonSelector
            onSelect={setSelectedSeason}
            selectedId={selectedSeason?.id}
          />
        </nav>
        {selectedSeason && (
          <nav className="view-tabs">
            <button
              className={currentView === "planner" ? "active" : ""}
              onClick={() => setCurrentView("planner")}
            >
              Planner
            </button>
            <button
              className={currentView === "statistics" ? "active" : ""}
              onClick={() => setCurrentView("statistics")}
            >
              Statistics
            </button>
            <button
              className={currentView === "members" ? "active" : ""}
              onClick={() => setCurrentView("members")}
            >
              Members
            </button>
            <a
              href={`/api/seasons/${selectedSeason.id}/export_pdf/`}
              className="export-pdf-btn"
            >
              Export PDF
            </a>
          </nav>
        )}
      </header>
      <main>
        {selectedSeason ? (
          <>
            {currentView === "planner" && <Planner season={selectedSeason} />}
            {currentView === "statistics" && <Statistics season={selectedSeason} />}
            {currentView === "members" && <MemberView />}
          </>
        ) : (
          <p className="placeholder">
            Select a season to view the planner.
            <br />
            Start by importing a schedule and member list.
          </p>
        )}
      </main>
      {importType && (
        <ImportModal
          type={importType}
          onClose={() => setImportType(null)}
          onSuccess={() => {
            setImportType(null);
            // Trigger season list refresh by clearing selection
            setSelectedSeason(null);
          }}
        />
      )}
    </div>
  );
}

export default App;
