import { useState, useCallback, useEffect } from "react";
import { useQuery } from "@tanstack/react-query";
import { SeasonSelector } from "./components/SeasonSelector";
import { Planner } from "./components/Planner";
import { Statistics } from "./components/Statistics";
import { MemberView } from "./components/MemberView";
import { Settings } from "./components/Settings";
import { Availability } from "./components/Availability";
import { ImportModal } from "./components/ImportModal";
import { AssignmentPanel } from "./components/AssignmentPanel";
import { Login } from "./components/Login";
import { ToastContextProvider, useToastContext } from "./components/ToastContext";
import { useToast } from "./components/Toast";
import { useTour } from "./tour/useTour";
import { clearAuth, getSiteConfig, getUser, getToken, logout } from "./api";
import type { Season } from "./types";
import type { TaskWithAssignments } from "./types";
import styles from "./App.module.css";
import "./styles/theme.css";
import "./styles/globals.css";

type View = "planner" | "statistics" | "members" | "settings" | "availability";

function AppInner() {
  const { addToast } = useToastContext();
  const [authenticated, setAuthenticated] = useState(!!getToken());
  const [user, setUser] = useState(getUser());
  const [selectedSeason, setSelectedSeason] = useState<Season | null>(null);
  const [importType, setImportType] = useState<"schedule" | "members" | null>(null);
  const [currentView, setCurrentView] = useState<View>("planner");
  const [selectedTask, setSelectedTask] = useState<
    { task: TaskWithAssignments; gameId: number } | null
  >(null);
  const [sidebarCollapsed, setSidebarCollapsed] = useState(
    () => localStorage.getItem("sidebar-collapsed") === "1"
  );

  // Interactive guided tour (issue #8): auto-starts on first login, replayable
  // via the Help entry below. Runs only while authenticated (the hook itself
  // stays inert on the login screen). The panel steps are included only when
  // a task is selected — the panel itself is always mounted (hidden when
  // closed), so its React state is the source of truth for "is it open".
  const { replay } = useTour(
    selectedSeason?.id ?? null,
    authenticated,
    !!selectedTask,
  );

  const handleToggleSidebar = useCallback(() => {
    setSidebarCollapsed((collapsed) => {
      localStorage.setItem("sidebar-collapsed", collapsed ? "0" : "1");
      return !collapsed;
    });
  }, []);

  // Listen for forced logout (401 from API)
  useEffect(() => {
    const handleLogout = () => {
      setAuthenticated(false);
      setUser(null);
    };
    window.addEventListener("auth:logout", handleLogout);
    return () => window.removeEventListener("auth:logout", handleLogout);
  }, []);

  // Club name from server-side site config (public read)
  const { data: siteConfig } = useQuery({
    queryKey: ["site-config"],
    queryFn: getSiteConfig,
  });
  const brand = siteConfig?.club_name ?? "";

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
    // Revoke the token server-side (best effort — we log out locally either way)
    void logout().catch(() => {});
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

  // Handle email verification from URL
  const verifyMatch = window.location.hash.match(/^#\/verify-email\/(.+)$/);
  if (verifyMatch && verifyMatch[1] && !authenticated) {
    return (
      <Login
        onLogin={handleLogin}
        brand={brand}
        initialVerifyToken={decodeURIComponent(verifyMatch[1])}
      />
    );
  }

  if (!authenticated) {
    return <Login onLogin={handleLogin} brand={brand} />;
  }

  return (
    <div className={styles.app}>
      {/* Top Bar */}
      <header className={styles["top-bar"]}>
        <div className={styles["top-bar-left"]}>
          <img src="/favicon.svg" alt="Logo" className={styles["logo-img"]} />
          <span className={styles.brand}>
            Hoops Planner
            {brand && (
              <>
                <span className={styles["brand-divider"]}>|</span> {brand}
              </>
            )}
          </span>
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
          <button
            className="icon-btn"
            onClick={replay}
            title="Replay the guided tour"
            aria-label="Help"
          >
            ? Help
          </button>
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
                    addToast("Email verified successfully!", "success");
                  } else {
                    addToast("Verification email sent.", "info");
                  }
                } catch (err) {
                  addToast(err instanceof Error ? err.message : "Failed to verify email", "error");
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
        <aside
          data-testid="sidebar"
          className={`${styles.sidebar} ${sidebarCollapsed ? styles["sidebar-collapsed"] : ""}`}
        >
          <nav>
            <button
              className={currentView === "planner" ? styles.active : ""}
              onClick={() => handleViewChange("planner")}
              aria-label="Schedule Planner"
              title="Schedule Planner"
            >
              <span className={styles["nav-icon"]}>📅</span>
              <span className={styles["nav-label"]}>Schedule Planner</span>
            </button>
            <button
              className={currentView === "members" ? styles.active : ""}
              onClick={() => handleViewChange("members")}
              aria-label="Member Roster"
              title="Member Roster"
            >
              <span className={styles["nav-icon"]}>👥</span>
              <span className={styles["nav-label"]}>Member Roster</span>
            </button>
            <button
              className={currentView === "statistics" ? styles.active : ""}
              onClick={() => handleViewChange("statistics")}
              aria-label="Statistics"
              title="Statistics"
            >
              <span className={styles["nav-icon"]}>📊</span>
              <span className={styles["nav-label"]}>Statistics</span>
            </button>
            <button
              className={currentView === "settings" ? styles.active : ""}
              onClick={() => handleViewChange("settings")}
              aria-label="Settings"
              title="Settings"
            >
              <span className={styles["nav-icon"]}>⚙️</span>
              <span className={styles["nav-label"]}>Settings</span>
            </button>
            <button
              className={currentView === "availability" ? styles.active : ""}
              onClick={() => handleViewChange("availability")}
              aria-label="Availability"
              title="Availability"
            >
              <span className={styles["nav-icon"]}>🚫</span>
              <span className={styles["nav-label"]}>Availability</span>
            </button>
          </nav>
          <div className={styles["sidebar-footer"]}>
            <button
              className="icon-btn"
              onClick={handleToggleSidebar}
              title={sidebarCollapsed ? "Expand sidebar" : "Collapse sidebar"}
              aria-label={sidebarCollapsed ? "Expand sidebar" : "Collapse sidebar"}
            >
              {sidebarCollapsed ? "»" : "«"}
            </button>
          </div>
        </aside>

        {/* Main Content */}
        <main className={styles["main-content"]}>
          {currentView === "settings" ? (
            <Settings isStaff={user?.is_staff ?? false} />
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
                  selectedGameId={selectedTask?.gameId}
                  selectedTaskId={selectedTask?.task.id}
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

        {/* Right Panel — always mounted so query cache stays warm */}
        <AssignmentPanel
          task={selectedTask?.task}
          gameId={selectedTask?.gameId}
          open={!!selectedTask}
          onClose={handleClosePanel}
        />
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

export function App() {
  const { toasts, addToast, removeToast } = useToast();

  return (
    <ToastContextProvider toasts={toasts} addToast={addToast} removeToast={removeToast}>
      <AppInner />
    </ToastContextProvider>
  );
}

export default App;
