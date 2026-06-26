import { useState, useCallback } from "react";
import { SeasonSelector } from "./components/SeasonSelector";
import { Planner } from "./components/Planner";
import { Statistics } from "./components/Statistics";
import { MemberView } from "./components/MemberView";
import { ImportModal } from "./components/ImportModal";
import { AssignmentPanel } from "./components/AssignmentPanel";
import type { Season } from "./types";
import type { TaskWithAssignments } from "./types";
import "./App.css";

type View = "planner" | "statistics" | "members" | "settings";

export function App() {
  const [selectedSeason, setSelectedSeason] = useState<Season | null>(null);
  const [importType, setImportType] = useState<"schedule" | "members" | null>(null);
  const [currentView, setCurrentView] = useState<View>("planner");
  const [selectedTask, setSelectedTask] = useState<
    { task: TaskWithAssignments; gameId: number } | null
  >(null);

  const handleSelectTask = useCallback(
    (task: TaskWithAssignments, gameId: number) => {
      setSelectedTask({ task, gameId });
    },
    []
  );

  const handleClosePanel = useCallback(() => {
    setSelectedTask(null);
  }, []);

  return (
    <div className="app">
      {/* Top Bar */}
      <header className="top-bar">
        <div className="top-bar-left">
          <img src="/logo.png" alt="BC Vido" className="logo-img" />
          <span className="brand">Hoops Planner <span className="brand-divider">|</span> BC Vido</span>
        </div>
        <div className="top-bar-right">
          <button
            className="icon-btn"
            onClick={() => setImportType("schedule")}
            title="Import Schedule"
          >
            Import Schedule
          </button>
          <button
            className="icon-btn"
            onClick={() => setImportType("members")}
            title="Import Members"
          >
            Import Members
          </button>
          <SeasonSelector
            onSelect={setSelectedSeason}
            selectedId={selectedSeason?.id}
          />
        </div>
      </header>

      <div className="app-body">
        {/* Sidebar */}
        <aside className="sidebar">
          <nav>
            <button
              className={currentView === "planner" ? "active" : ""}
              onClick={() => setCurrentView("planner")}
            >
              <span className="nav-icon">📅</span>
              Schedule Planner
            </button>
            <button
              className={currentView === "members" ? "active" : ""}
              onClick={() => setCurrentView("members")}
            >
              <span className="nav-icon">👥</span>
              Member Roster
            </button>
            <button
              className={currentView === "statistics" ? "active" : ""}
              onClick={() => setCurrentView("statistics")}
            >
              <span className="nav-icon">📊</span>
              Statistics
            </button>
          </nav>
        </aside>

        {/* Main Content */}
        <main className="main-content">
          {selectedSeason ? (
            <>
              {currentView === "planner" && (
                <Planner
                  season={selectedSeason}
                  onSelectTask={handleSelectTask}
                />
              )}
              {currentView === "statistics" && <Statistics season={selectedSeason} />}
              {currentView === "members" && <MemberView />}
            </>
          ) : currentView === "members" ? (
            <MemberView />
          ) : (
            <div className="empty-state">
              <h2>Welcome to Hoops Planner</h2>
              <p>Select a season to view the planner.</p>
              <p>Start by importing a schedule and member list.</p>
            </div>
          )}
        </main>

        {/* Right Panel */}
        {selectedTask && (
          <AssignmentPanel
            task={selectedTask.task}
            gameId={selectedTask.gameId}
            onClose={handleClosePanel}
          />
        )}
      </div>

      {importType && (
        <ImportModal
          type={importType}
          onClose={() => setImportType(null)}
          onSuccess={() => {
            setImportType(null);
            // Keep the current season selected so the user sees their data immediately
          }}
        />
      )}
    </div>
  );
}

export default App;
