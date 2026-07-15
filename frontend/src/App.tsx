import { useState, useCallback, useEffect } from "react";
import { SeasonSelector } from "./components/SeasonSelector";
import { Planner } from "./components/Planner";
import { Statistics } from "./components/Statistics";
import { MemberView } from "./components/MemberView";
import { Settings } from "./components/Settings";
import { ImportModal } from "./components/ImportModal";
import { AssignmentPanel } from "./components/AssignmentPanel";
import { Login } from "./components/Login";
import { clearAuth, getUser, getToken } from "./api";
import type { Season } from "./types";
import type { TaskWithAssignments } from "./types";
import "./App.css";

type View = "planner" | "statistics" | "members" | "settings";

export function App() {
  const [authenticated, setAuthenticated] = useState(!!getToken());
  const [user, setUser] = useState(getUser());
  const [selectedSeason, setSelectedSeason] = useState<Season | null>(null);
  const [importType, setImportType] = useState<"schedule" | "members" | null>(null);
  const [currentView, setCurrentView] = useState<View>("planner");
  const [selectedTask, setSelectedTask] = useState<
    { task: TaskWithAssignments; gameId: number } | null
  >(null);

  // Listen for forced logout (401 from API)
  useEffect(() => {
    const handleLogout = () => {
      setAuthenticated(false);
      setUser(null);
    };
    window.addEventListener("auth:logout", handleLogout);
    return () => window.removeEventListener("auth:logout", handleLogout);
  }, []);

  // Close assignment panel when switching views
  const handleViewChange = useCallback((view: View) => {
    setCurrentView(view);
    setSelectedTask(null);
  }, []);

  const handleLogin = useCallback(() => {
    setAuthenticated(true);
    setUser(getUser());
  }, []);

  const handleLogout = useCallback(() => {
    clearAuth();
    setAuthenticated(false);
    setUser(null);
  }, []);

  const handleSelectTask = useCallback(
    (task: TaskWithAssignments, gameId: number) => {
      setSelectedTask({ task, gameId });
    },
    []
  );

  const handleClosePanel = useCallback(() => {
    setSelectedTask(null);
  }, []);

  if (!authenticated) {
    return <Login onLogin={handleLogin} />;
  }

  return (
    <div className="app">
      {/* Top Bar */}
      <header className="top-bar">
        <div className="top-bar-left">
          <img src="/logo.png" alt="BC Vido" className="logo-img" />
          <span className="brand">Sixth Man <span className="brand-divider">|</span> BC Vido</span>
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
          <span className="user-badge" title={user?.username}>
            {user?.username}
          </span>
          <button className="icon-btn logout-btn" onClick={handleLogout} title="Logout">
            Logout
          </button>
        </div>
      </header>

      <div className="app-body">
        {/* Sidebar */}
        <aside className="sidebar">
          <nav>
            <button
              className={currentView === "planner" ? "active" : ""}
              onClick={() => handleViewChange("planner")}
            >
              <span className="nav-icon">📅</span>
              Schedule Planner
            </button>
            <button
              className={currentView === "members" ? "active" : ""}
              onClick={() => handleViewChange("members")}
            >
              <span className="nav-icon">👥</span>
              Member Roster
            </button>
            <button
              className={currentView === "statistics" ? "active" : ""}
              onClick={() => handleViewChange("statistics")}
            >
              <span className="nav-icon">📊</span>
              Statistics
            </button>
            <button
              className={currentView === "settings" ? "active" : ""}
              onClick={() => handleViewChange("settings")}
            >
              <span className="nav-icon">⚙️</span>
              Settings
            </button>
          </nav>
        </aside>

        {/* Main Content */}
        <main className="main-content">
          {currentView === "settings" ? (
            <Settings />
          ) : selectedSeason ? (
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
              <h2>Welcome to Sixth Man</h2>
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
