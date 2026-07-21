import { useState, useCallback, useEffect } from "react";
import { SeasonSelector } from "./components/SeasonSelector";
import { Planner } from "./components/Planner";
import { Statistics } from "./components/Statistics";
import { MemberView } from "./components/MemberView";
import { Settings } from "./components/Settings";
import { Availability } from "./components/Availability";
import { ImportModal } from "./components/ImportModal";
import { AssignmentPanel } from "./components/AssignmentPanel";
import { Login } from "./components/Login";
import { clearAuth, getUser, getToken } from "./api";
import type { Season } from "./types";
import type { TaskWithAssignments } from "./types";
import styles from "./App.module.css";
import "./styles/globals.css";

type View = "planner" | "statistics" | "members" | "settings" | "availability";

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
    <div className={styles.app}>
      {/* Top Bar */}
      <header className={styles["top-bar"]}>
        <div className={styles["top-bar-left"]}>
          <img src="/logo.png" alt="BC Vido" className={styles["logo-img"]} />
          <span className={styles.brand}>Sixth Man <span className={styles["brand-divider"]}>|</span> BC Vido</span>
        </div>
        <div className={styles["top-bar-right"]}>
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
          {user?.email && (
            <button
              className="icon-btn"
              onClick={async () => {
                try {
                  const { verifyEmailRequest, verifyEmailConfirm } = await import("./api");
                  const data = await verifyEmailRequest();
                  if (data.token) {
                    await verifyEmailConfirm(data.token);
                    alert("Email verified successfully!");
                  } else {
                    alert("Verification email sent.");
                  }
                } catch (err) {
                  alert(err instanceof Error ? err.message : "Failed to verify email");
                }
              }}
              title="Verify Email"
            >
              Verify Email
            </button>
          )}
          <button className="icon-btn logout-btn" onClick={handleLogout} title="Logout">
            Logout
          </button>
        </div>
      </header>

      <div className={styles["app-body"]}>
        {/* Sidebar */}
        <aside className={styles.sidebar}>
          <nav>
            <button
              className={currentView === "planner" ? styles.active : ""}
              onClick={() => handleViewChange("planner")}
            >
              <span className={styles["nav-icon"]}>📅</span>
              Schedule Planner
            </button>
            <button
              className={currentView === "members" ? styles.active : ""}
              onClick={() => handleViewChange("members")}
            >
              <span className={styles["nav-icon"]}>👥</span>
              Member Roster
            </button>
            <button
              className={currentView === "statistics" ? styles.active : ""}
              onClick={() => handleViewChange("statistics")}
            >
              <span className={styles["nav-icon"]}>📊</span>
              Statistics
            </button>
            <button
              className={currentView === "settings" ? styles.active : ""}
              onClick={() => handleViewChange("settings")}
            >
              <span className={styles["nav-icon"]}>⚙️</span>
              Settings
            </button>
            <button
              className={currentView === "availability" ? styles.active : ""}
              onClick={() => handleViewChange("availability")}
            >
              <span className={styles["nav-icon"]}>🚫</span>
              Availability
            </button>
          </nav>
        </aside>

        {/* Main Content */}
        <main className={styles["main-content"]}>
          {currentView === "settings" ? (
            <Settings />
          ) : currentView === "availability" ? (
            selectedSeason ? (
              <Availability season={selectedSeason} />
            ) : (
              <div className="empty-state">
                <h2>Select a season</h2>
                <p>Choose a season to view availability.</p>
              </div>
            )
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
