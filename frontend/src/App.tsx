import { useState } from "react";
import { SeasonSelector } from "./components/SeasonSelector";
import { Planner } from "./components/Planner";
import { ImportModal } from "./components/ImportModal";
import type { Season } from "./types";
import "./App.css";

export function App() {
  const [selectedSeason, setSelectedSeason] = useState<Season | null>(null);
  const [importType, setImportType] = useState<"schedule" | "members" | null>(null);

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
      </header>
      <main>
        {selectedSeason ? (
          <Planner season={selectedSeason} />
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
